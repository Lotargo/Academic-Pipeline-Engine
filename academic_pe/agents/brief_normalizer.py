from __future__ import annotations

import json
from typing import Dict, Optional

from academic_pe.agents.base import BaseAgent, StreamCallback
from academic_pe.core.llm import _call_provider_generate
from academic_pe.instructions.brief import NormalizedBrief, parse_normalized_brief


class BriefNormalizerAgent(BaseAgent):
    """Extracts a NormalizedBrief in one bounded pass; it does not author prompts."""

    last_normalized_brief: NormalizedBrief | None = None

    def process(
        self,
        task_description: str,
        context: Optional[str] = None,
        on_delta: Optional[StreamCallback] = None,
        document_sections: Optional[Dict[str, str]] = None,
    ) -> str:
        raw = _call_provider_generate(
            self.llm,
            system_prompt=self.config.system_prompt,
            user_prompt=task_description,
            model=self.config.model,
            temperature=self.config.temperature,
            on_delta=on_delta,
            reasoning_effort=getattr(self.config.reasoning_effort, "value", self.config.reasoning_effort),
        )
        try:
            brief = parse_normalized_brief(raw)
        except Exception:
            brief = _fallback_brief(task_description)
        self.last_normalized_brief = brief
        self.last_self_critique_summary = None
        return json.dumps(brief.model_dump(mode="json"), ensure_ascii=False)


def _fallback_brief(task: str) -> NormalizedBrief:
    topic = ""
    instructions = ""
    for line in task.splitlines():
        if line.startswith("Raw topic:"):
            topic = line.partition(":")[2].strip()
        elif line.startswith("Raw instructions:"):
            instructions = line.partition(":")[2].strip()
    return NormalizedBrief(
        topic=topic or "Untitled artifact",
        explicit_requirements=[instructions] if instructions else [],
        unresolved_ambiguities=["normalizer_model_response_invalid"],
    )
