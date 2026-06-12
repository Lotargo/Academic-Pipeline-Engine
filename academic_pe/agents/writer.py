import re
from typing import Callable, Optional

from academic_pe.agents.base import BaseAgent
from academic_pe.core.llm import _call_provider_generate

StreamCallback = Callable[[str], None]


class WriterAgent(BaseAgent):
    def process(
        self,
        task_description: str,
        context: Optional[str] = None,
        on_delta: Optional[StreamCallback] = None,
    ) -> str:
        system_prompt = self.config.system_prompt
        if context:
            system_prompt += (
                "\n\n[Context Data]\n"
                "Use the following existing content as reference. "
                "Maintain consistency in style and terminology.\n"
                f"{context}"
            )

        return _call_provider_generate(
            self.llm,
            system_prompt=system_prompt,
            user_prompt=task_description,
            model=self.config.model,
            temperature=self.config.temperature,
            on_delta=on_delta,
        )


class ReviewerAgent(BaseAgent):
    _APPROVED_PATTERN = re.compile(r"^\s*APPROVED\s*$", re.IGNORECASE)

    def process(
        self,
        task_description: str,
        context: Optional[str] = None,
        on_delta: Optional[StreamCallback] = None,
    ) -> str:
        system_prompt = self.config.system_prompt
        if context:
            system_prompt += f"\n\n[Text to Review]\n{context}"

        raw = self.llm.generate(
            system_prompt=system_prompt,
            user_prompt=task_description,
            model=self.config.model,
            temperature=self.config.temperature,
        )
        return raw.strip()

    def is_approved(self, feedback: str) -> bool:
        return bool(self._APPROVED_PATTERN.match(feedback))

    def parse_reason(self, feedback: str) -> str:
        if self.is_approved(feedback):
            return ""
        match = re.match(r"REJECTED[:\s]+(.+)", feedback, re.IGNORECASE)
        return match.group(1).strip() if match else feedback
