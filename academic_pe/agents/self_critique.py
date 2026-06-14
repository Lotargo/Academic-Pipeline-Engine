from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional

from academic_pe.core.config import AgentConfig
from academic_pe.core.llm import LLMProvider, _call_provider_generate


@dataclass(frozen=True)
class SelfCritiqueResult:
    output: str
    summary: str = ""
    changed: bool = False
    skipped_reason: str = ""


def run_self_critique(
    *,
    agent_name: str,
    config: AgentConfig,
    llm: LLMProvider,
    task_description: str,
    draft_output: str,
    system_prompt: str,
    context: Optional[str] = None,
) -> SelfCritiqueResult:
    critique_config = config.self_critique
    if not critique_config.enabled:
        return SelfCritiqueResult(output=draft_output, skipped_reason="disabled")

    if not draft_output.strip():
        return SelfCritiqueResult(output=draft_output, skipped_reason="empty_draft")

    prompt = _build_self_critique_prompt(
        agent_name=agent_name,
        task_description=task_description,
        draft_output=draft_output,
        system_prompt=system_prompt,
        context=context,
    )
    temperature = config.temperature if critique_config.temperature is None else critique_config.temperature

    raw = _call_provider_generate(
        llm,
        system_prompt=_SELF_CRITIQUE_SYSTEM_PROMPT,
        user_prompt=prompt,
        model=config.model,
        temperature=temperature,
    )

    parsed = _parse_self_critique_response(raw)
    if parsed is None:
        return SelfCritiqueResult(
            output=draft_output,
            summary="Self-critique skipped: invalid critic response.",
            skipped_reason="invalid_response",
        )

    summary, repaired = parsed
    if not repaired.strip():
        return SelfCritiqueResult(
            output=draft_output,
            summary="Self-critique skipped: empty repair.",
            skipped_reason="empty_repair",
        )
    if _looks_like_blocking_feedback(repaired):
        return SelfCritiqueResult(
            output=draft_output,
            summary="Self-critique skipped: critic returned blocking feedback.",
            skipped_reason="blocking_feedback",
        )

    repaired = repaired.strip()
    return SelfCritiqueResult(
        output=repaired,
        summary=_short_summary(summary),
        changed=repaired != draft_output.strip(),
    )


_SELF_CRITIQUE_SYSTEM_PROMPT = """You are an internal, non-blocking self-critique pass.
Your job is to repair the agent's own draft directly before it is handed forward.
Do not ask the user for approval. Do not return REJECTED, TODOs, review notes, or explanations.
Do not reveal chain-of-thought. Return ONLY a compact JSON object:
{"summary":"short factual repair summary, max 160 characters","output":"final repaired output"}
"""


def _build_self_critique_prompt(
    *,
    agent_name: str,
    task_description: str,
    draft_output: str,
    system_prompt: str,
    context: Optional[str],
) -> str:
    agent_rules = _agent_rules(agent_name)
    is_academic = "academic_mode" in system_prompt or "execution_mode academic" in system_prompt
    
    academic_rules = ""
    if is_academic:
        academic_rules = (
            "\nStrong academic-mode critical thinking rules:\n"
            "- Identify and repair weak assumptions, unsupported claims, or conceptual contradictions.\n"
            "- Avoid shallow definitions; ensure methodological clarity and conceptual precision.\n"
            "- Call out and describe limitations of the analysis or method where appropriate.\n"
            "- Verify that necessary source/evidence gaps are repaired directly if the contract requires evidence/sources."
        )

    context_block = f"\n\n[Context]\n{context}" if context else ""
    return (
        f"Agent: {agent_name}\n"
        f"{agent_rules}\n"
        f"{academic_rules}\n\n"
        "[Active System Prompt And Contract]\n"
        f"{system_prompt}\n"
        f"{context_block}\n\n"
        "[Original Task]\n"
        f"{task_description}\n\n"
        "[Draft Output]\n"
        f"{draft_output}\n\n"
        "Repair the draft in one pass. If it already satisfies the task and contract, return it unchanged."
    )


def _agent_rules(agent_name: str) -> str:
    normalized = agent_name.strip().lower()
    if normalized == "planner":
        return (
            "Planner self-critique: ensure the plan/template follows the active manifest, preserves genre/style, "
            "avoids academic drift, handles continuation, and remains valid JSON when JSON was requested."
        )
    if normalized == "writer":
        return (
            "Writer self-critique: ensure the draft obeys the contract, preserves voice/genre/audience, satisfies "
            "user constraints, avoids AI/meta markers, and keeps academic_mode rigor compatible with the artifact."
        )
    if normalized == "prompt_enhancer":
        return (
            "PromptEnhancer self-critique: ensure the enhancement preserves artifact type, keeps user details, "
            "and does not add bureaucracy or unrelated academic structure."
        )
    if normalized == "researcher":
        return (
            "Researcher self-critique: check source relevance, citation quality, and evidence overreach. "
            "Avoid forcing citations or bibliography into non-academic/creative works unless requested. "
            "Directly rewrite findings to repair any issues."
        )
    if normalized in {"exporter", "renderer"}:
        return (
            "Exporter/renderer self-critique: check structure and format compatibility against the contract. "
            "Ensure proper headings, spacing, and output constraints without adding title pages, rubrics, "
            "or academic apparatus unless requested. Directly rewrite to fix formatting."
        )
    return "Self-critique: repair only material contract, consistency, style, and user-constraint issues."


def _parse_self_critique_response(raw: str) -> tuple[str, str] | None:
    try:
        data = json.loads(_extract_json_object(raw))
    except (json.JSONDecodeError, TypeError):
        return None

    if not isinstance(data, dict):
        return None
    output = data.get("output")
    if not isinstance(output, str):
        return None
    summary = data.get("summary", "")
    if not isinstance(summary, str):
        summary = str(summary)
    return summary, output


def _extract_json_object(raw: str) -> str:
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return text
    return text[start : end + 1]


def _looks_like_blocking_feedback(text: str) -> bool:
    stripped = text.strip()
    return bool(re.match(r"^(REJECTED|BLOCKED|NEEDS_USER|ASK_USER)\b", stripped, flags=re.IGNORECASE))


def _short_summary(summary: str) -> str:
    compact = " ".join(summary.split())
    if len(compact) <= 160:
        return compact
    return compact[:157].rstrip() + "..."
