from __future__ import annotations

from abc import ABC, abstractmethod
import os
from typing import Optional

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


class CustomOpenAIProvider(LLMProvider):
    def __init__(self, base_url: str, api_key_env: str = "CUSTOM_API_KEY"):
        api_key = os.getenv(api_key_env, "sk-placeholder")
        self._client = OpenAI(api_key=api_key, base_url=base_url)

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


class AnthropicProvider(LLMProvider):
    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable is not set."
            )
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError(
                "anthropic package is required for AnthropicProvider. "
                "Install it with: pip install anthropic"
            )
        self._client = Anthropic(api_key=api_key)

    def generate(self, system_prompt: str, user_prompt: str, model: str, temperature: float) -> str:
        message = self._client.messages.create(
            model=model,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            temperature=temperature,
            max_tokens=4096,
        )
        return message.content[0].text if message.content else ""


class MockProvider(LLMProvider):
    def generate(self, system_prompt: str, user_prompt: str, model: str, temperature: float) -> str:
        return (
            f"# Generated Section\n\n"
            f"This is a mock response for prompt: {user_prompt[:60]}...\n\n"
            f"System prompt used: {system_prompt[:60]}...\n"
            f"Model: {model}, Temperature: {temperature}"
        )


_PROVIDER_REGISTRY: dict[str, type[LLMProvider]] = {
    "mock": MockProvider,
    "openai": OpenAIProvider,
    "custom_openai": CustomOpenAIProvider,
    "anthropic": AnthropicProvider,
}


def register_provider(name: str, provider_cls: type[LLMProvider]) -> None:
    _PROVIDER_REGISTRY[name] = provider_cls


def create_provider(
    provider: str = "mock",
    base_url: Optional[str] = None,
) -> LLMProvider:
    cls = _PROVIDER_REGISTRY.get(provider)
    if cls is None:
        raise ValueError(
            f"Unknown provider: {provider}. "
            f"Available: {list(_PROVIDER_REGISTRY)}"
        )

    if provider == "custom_openai":
        if not base_url:
            raise ValueError("base_url is required for custom_openai provider")
        return cls(base_url=base_url)

    return cls()
