from abc import ABC, abstractmethod
from typing import Optional

from src.core.config import AgentConfig
from src.core.llm import LLMProvider


class BaseAgent(ABC):
    def __init__(self, config: AgentConfig, llm: LLMProvider):
        self.config = config
        self.llm = llm

    @abstractmethod
    def process(self, task_description: str, context: Optional[str] = None) -> str:
        ...


class DefaultAgent(BaseAgent):
    def process(self, task_description: str, context: Optional[str] = None) -> str:
        system_prompt = self.config.system_prompt
        if context:
            system_prompt += f"\n\n[Context Data]\n{context}"

        return self.llm.generate(
            system_prompt=system_prompt,
            user_prompt=task_description,
            model=self.config.model,
            temperature=self.config.temperature,
        )
