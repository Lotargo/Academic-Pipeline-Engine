from __future__ import annotations

import json
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

        # Robust fallback parsing to extract a single candidate if self-critique failed to narrow down
        try:
            raw_output = result.output.strip()
            # Clean possible markdown block formatting
            if "```" in raw_output:
                import re
                match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw_output, re.DOTALL)
                if match:
                    raw_output = match.group(1).strip()
            data = json.loads(raw_output)
            if "conservative" in data or "detailed" in data or "creative" in data:
                selected = data.get("detailed") or data.get("conservative") or data.get("creative")
                if isinstance(selected, dict) and "topic" in selected and "instructions" in selected:
                    return json.dumps(selected)
        except Exception:
            pass

        return result.output
