from abc import ABC, abstractmethod
import os
from openai import OpenAI


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str, model: str, temperature: float) -> str:
        ...


class OpenAIProvider(LLMProvider):
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable is not set. "
                "Use MockProvider for testing or set the variable."
            )
        self._client = OpenAI(api_key=api_key)

    def generate(self, system_prompt: str, user_prompt: str, model: str, temperature: float) -> str:
        response = self._client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
        )
        return response.choices[0].message.content or ""


class MockProvider(LLMProvider):
    def generate(self, system_prompt: str, user_prompt: str, model: str, temperature: float) -> str:
        return (
            f"# Generated Section\n\n"
            f"This is a mock response for prompt: {user_prompt[:60]}...\n\n"
            f"System prompt used: {system_prompt[:60]}...\n"
            f"Model: {model}, Temperature: {temperature}"
        )
