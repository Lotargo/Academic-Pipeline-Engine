from __future__ import annotations

import json
import re
from typing import Callable, Dict, Optional

from academic_pe.agents.base import BaseAgent
from academic_pe.agents.self_critique import run_self_critique
from academic_pe.core.llm import _call_provider_generate

StreamCallback = Callable[[str], None]


class PromptEnhancerAgent(BaseAgent):
    def process(
        self,
        task_description: str,
        context: Optional[str] = None,
        on_delta: Optional[StreamCallback] = None,
        document_sections: Optional[Dict[str, str]] = None,
    ) -> str:
        system_prompt = self.config.system_prompt
        if context:
            system_prompt += f"\n\n[Context Data]\n{context}"

        # Request 3 candidate enhancements for ToT selection
        tot_user_prompt = (
            f"Raw User Task:\n{task_description}\n\n"
            "INSTRUCTION FOR CANDIDATE GENERATION:\n"
            "You must generate three diverse candidate prompt enhancements for the Raw User Task:\n"
            "1. 'conservative': preserves the raw request exactly, with minimal edits.\n"
            "2. 'detailed': adds detailed guidelines and structure clarifications without expanding scope or adding bureaucracy.\n"
            "3. 'creative': proposes creative/structural layouts compatible with the contract.\n\n"
            "These candidate labels are selection strategies, not allowed artifact categories. Do not treat examples or "
            "candidate labels as exhaustive; preserve any niche or unknown artifact form from the raw task.\n\n"
            "Return ONLY a JSON mapping containing these three candidates:\n"
            "{\n"
            "  \"conservative\": {\"topic\": \"...\", \"instructions\": \"...\"},\n"
            "  \"detailed\": {\"topic\": \"...\", \"instructions\": \"...\"},\n"
            "  \"creative\": {\"topic\": \"...\", \"instructions\": \"...\"}\n"
            "}"
        )

        draft = _call_provider_generate(
            self.llm,
            system_prompt=system_prompt,
            user_prompt=tot_user_prompt,
            model=self.config.model,
            temperature=self.config.temperature,
            on_delta=on_delta,
        )

        result = run_self_critique(
            agent_name="prompt_enhancer",
            config=self.config,
            llm=self.llm,
            task_description=task_description,
            draft_output=draft,
            system_prompt=system_prompt,
            context=context,
        )

        self.last_self_critique_summary = result.summary or None

        selected = _select_candidate_from_tot_response(result.output)
        if selected is not None:
            return json.dumps(selected)

        return result.output


def _select_candidate_from_tot_response(raw_output: str) -> Optional[dict[str, str]]:
    try:
        data = json.loads(_extract_json(raw_output))
    except (json.JSONDecodeError, TypeError):
        return None

    if not isinstance(data, dict):
        return None

    if _is_final_candidate(data):
        return {
            "topic": data["topic"].strip(),
            "instructions": data["instructions"].strip(),
        }

    for key in ["detailed", "conservative", "creative"]:
        candidate = data.get(key)
        if _is_final_candidate(candidate) and not _candidate_has_obvious_drift(candidate):
            return {
                "topic": candidate["topic"].strip(),
                "instructions": candidate["instructions"].strip(),
            }

    return None


def _extract_json(raw_output: str) -> str:
    text = raw_output.strip()
    if "```" in text:
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return text


def _is_final_candidate(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    topic = value.get("topic")
    instructions = value.get("instructions")
    return isinstance(topic, str) and bool(topic.strip()) and isinstance(instructions, str) and bool(instructions.strip())


def _candidate_has_obvious_drift(candidate: dict[str, str]) -> bool:
    text = f"{candidate.get('topic', '')}\n{candidate.get('instructions', '')}".casefold()
    forbidden_patterns = [
        r"\btitle page\b",
        r"\brubric\b",
        r"\bgrading criteria\b",
        r"\bworks cited\b",
        r"\bbibliography\b",
        r"\breferences section\b",
        r"\bas an ai\b",
        r"\bas a language model\b",
        r"\[insert [^\]]+\]",
        r"\[placeholder[^\]]*\]",
        r"\bprint and bind\b",
        r"\bphysical submission\b",
    ]
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in forbidden_patterns)
