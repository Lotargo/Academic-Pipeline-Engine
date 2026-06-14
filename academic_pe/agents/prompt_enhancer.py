from __future__ import annotations

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

        draft = _call_provider_generate(
            self.llm,
            system_prompt=system_prompt,
            user_prompt=task_description,
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
        return result.output
