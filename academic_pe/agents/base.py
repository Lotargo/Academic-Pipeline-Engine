from abc import ABC, abstractmethod
from typing import Callable, Optional

from academic_pe.core.config import AgentConfig
from academic_pe.core.llm import LLMProvider, _call_provider_generate
from academic_pe.agents.self_critique import run_self_critique

from typing import Callable, Optional, Dict

StreamCallback = Callable[[str], None]


class BaseAgent(ABC):
    def __init__(self, config: AgentConfig, llm: LLMProvider):
        self.config = config
        self.llm = llm
        self.last_self_critique_summary: Optional[str] = None

    @abstractmethod
    def process(
        self,
        task_description: str,
        context: Optional[str] = None,
        on_delta: Optional[StreamCallback] = None,
        document_sections: Optional[Dict[str, str]] = None,
    ) -> str:
        ...


class DefaultAgent(BaseAgent):
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
            reasoning_effort=getattr(self.config.reasoning_effort, "value", self.config.reasoning_effort),
        )
        result = run_self_critique(
            agent_name=self.config.role or "default",
            config=self.config,
            llm=self.llm,
            task_description=task_description,
            draft_output=draft,
            system_prompt=system_prompt,
            context=context,
        )
        self.last_self_critique_summary = result.summary or None
        return result.output
