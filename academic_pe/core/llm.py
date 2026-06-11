from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
import os
from typing import Optional

from openai import OpenAI

logger = logging.getLogger(__name__)


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


@dataclass
class RetryConfig:
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0


class RetryProvider(LLMProvider):
    def __init__(self, inner: LLMProvider, config: RetryConfig = RetryConfig()):
        self._inner = inner
        self._config = config

    def generate(self, system_prompt: str, user_prompt: str, model: str, temperature: float) -> str:
        if self._config.max_retries <= 0:
            return self._inner.generate(system_prompt, user_prompt, model, temperature)

        last_error: Optional[Exception] = None

        for attempt in range(self._config.max_retries):
            try:
                return self._inner.generate(system_prompt, user_prompt, model, temperature)
            except Exception as e:
                last_error = e
                if attempt < self._config.max_retries - 1:
                    delay = min(self._config.base_delay * (2 ** attempt), self._config.max_delay)
                    logger.warning(
                        "LLM call failed (attempt %d/%d): %s. Retrying in %.1fs...",
                        attempt + 1, self._config.max_retries, e, delay,
                    )
                    time.sleep(delay)

        raise last_error  # type: ignore[misc]


class CircuitState(Enum):
    CLOSED = auto()
    OPEN = auto()
    HALF_OPEN = auto()


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    recovery_timeout: float = 30.0


class CircuitBreakerProvider(LLMProvider):
    def __init__(self, inner: LLMProvider, config: CircuitBreakerConfig = CircuitBreakerConfig()):
        self._inner = inner
        self._config = config
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self._config.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker: OPEN -> HALF_OPEN")
        return self._state

    def generate(self, system_prompt: str, user_prompt: str, model: str, temperature: float) -> str:
        current_state = self.state
        if current_state == CircuitState.OPEN:
            raise RuntimeError(
                f"Circuit breaker is OPEN. "
                f"Retry after {self._config.recovery_timeout}s."
            )

        try:
            result = self._inner.generate(system_prompt, user_prompt, model, temperature)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        self._failure_count = 0
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
            logger.info("Circuit breaker: HALF_OPEN -> CLOSED")

    def _on_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self._config.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                "Circuit breaker: CLOSED -> OPEN after %d failures",
                self._failure_count,
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
    retry_config: Optional[RetryConfig] = None,
    circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
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
        instance: LLMProvider = cls(base_url=base_url)
    else:
        instance = cls()

    if retry_config is not None and retry_config.max_retries > 0:
        instance = RetryProvider(instance, retry_config)

    if circuit_breaker_config is not None and circuit_breaker_config.enabled:
        instance = CircuitBreakerProvider(
            instance,
            CircuitBreakerConfig(
                failure_threshold=circuit_breaker_config.failure_threshold,
                recovery_timeout=circuit_breaker_config.recovery_timeout,
            ),
        )

    return instance
