from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
import os
import threading
from typing import Callable, Optional, Union, Any

from openai import OpenAI

logger = logging.getLogger(__name__)

StreamCallback = Callable[[str], None]

_OPENAI_CLIENT_CACHE: dict[tuple[str, str], OpenAI] = {}
_OPENAI_CLIENT_CACHE_LOCK = threading.Lock()
_REASONING_UNSUPPORTED_TTL_SECONDS = 60 * 60
_REASONING_UNSUPPORTED_CACHE: dict[tuple[str, str], float] = {}
_REASONING_UNSUPPORTED_CACHE_LOCK = threading.Lock()


def _get_openai_client(api_key: str, base_url: Optional[str] = None) -> OpenAI:
    cache_key = (api_key, base_url or "")
    with _OPENAI_CLIENT_CACHE_LOCK:
        client = _OPENAI_CLIENT_CACHE.get(cache_key)
        if client is None:
            if base_url:
                client = OpenAI(api_key=api_key, base_url=base_url)
            else:
                client = OpenAI(api_key=api_key)
            _OPENAI_CLIENT_CACHE[cache_key] = client
        return client


def _openai_chat_generate(
    client: OpenAI,
    system_prompt: str,
    user_prompt: str,
    model: str,
    temperature: float,
    on_delta: Optional[StreamCallback] = None,
    reasoning_effort: Optional[str] = None,
) -> str:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    request_kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    effort = normalize_reasoning_effort(model, reasoning_effort)
    if effort and not _is_reasoning_effort_cached_unsupported(client, model):
        request_kwargs["reasoning_effort"] = effort

    if on_delta is None:
        response = _create_openai_chat_completion(client, request_kwargs)
        return response.choices[0].message.content or ""

    chunks: list[str] = []
    stream = _create_openai_chat_completion(client, {**request_kwargs, "stream": True})
    for event in stream:
        delta = event.choices[0].delta.content or ""
        if delta:
            chunks.append(delta)
            on_delta(delta)
    return "".join(chunks)


def normalize_reasoning_effort(model: str, reasoning_effort: Optional[str]) -> Optional[str]:
    if reasoning_effort is None:
        return None
    effort = str(reasoning_effort).strip().lower()
    if not effort or effort in {"default", "provider_default", "none"}:
        return None
    if effort not in {"low", "medium", "high", "max"}:
        return None
    if effort == "max" and "deepseek-v4" not in (model or "").lower():
        return "high"
    return effort


def _create_openai_chat_completion(client: OpenAI, request_kwargs: dict[str, Any]) -> Any:
    try:
        return client.chat.completions.create(**request_kwargs)
    except Exception as exc:
        if "reasoning_effort" not in request_kwargs:
            raise
        message = str(exc).lower()
        unsupported_markers = (
            "reasoning",
            "reasoning_effort",
            "unsupported",
            "unrecognized",
            "unknown parameter",
            "extra inputs",
        )
        if not any(marker in message for marker in unsupported_markers):
            raise
        fallback_kwargs = dict(request_kwargs)
        effort = fallback_kwargs.pop("reasoning_effort", None)
        _remember_reasoning_effort_unsupported(client, str(fallback_kwargs.get("model") or ""))
        logger.warning(
            "Provider rejected reasoning_effort=%s for model %s; retrying without it.",
            effort,
            fallback_kwargs.get("model"),
        )
        return client.chat.completions.create(**fallback_kwargs)


def _reasoning_cache_key(client: OpenAI, model: str) -> tuple[str, str]:
    return (str(getattr(client, "base_url", "") or ""), model)


def _is_reasoning_effort_cached_unsupported(client: OpenAI, model: str) -> bool:
    key = _reasoning_cache_key(client, model)
    now = time.monotonic()
    with _REASONING_UNSUPPORTED_CACHE_LOCK:
        expires_at = _REASONING_UNSUPPORTED_CACHE.get(key)
        if expires_at is None:
            return False
        if expires_at <= now:
            _REASONING_UNSUPPORTED_CACHE.pop(key, None)
            return False
        return True


def _remember_reasoning_effort_unsupported(client: OpenAI, model: str) -> None:
    if not model:
        return
    key = _reasoning_cache_key(client, model)
    with _REASONING_UNSUPPORTED_CACHE_LOCK:
        _REASONING_UNSUPPORTED_CACHE[key] = time.monotonic() + _REASONING_UNSUPPORTED_TTL_SECONDS


def _call_provider_generate(
    provider: "LLMProvider",
    system_prompt: str,
    user_prompt: str,
    model: str,
    temperature: float,
    on_delta: Optional[StreamCallback] = None,
    reasoning_effort: Optional[str] = None,
) -> str:
    call_kwargs = {
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "model": model,
        "temperature": temperature,
        "reasoning_effort": reasoning_effort,
    }
    if on_delta is not None:
        call_kwargs["on_delta"] = on_delta

    try:
        return provider.generate(**call_kwargs)
    except TypeError as exc:
        if "reasoning_effort" not in str(exc):
            raise

    if on_delta is None:
        return provider.generate(system_prompt, user_prompt, model, temperature)
    try:
        return provider.generate(system_prompt, user_prompt, model, temperature, on_delta=on_delta)
    except TypeError as exc:
        if "on_delta" not in str(exc):
            raise
        result = provider.generate(system_prompt, user_prompt, model, temperature)
        if result:
            on_delta(result)
        return result


class LLMProvider(ABC):
    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
        on_delta: Optional[StreamCallback] = None,
        reasoning_effort: Optional[str] = None,
    ) -> str:
        ...


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: Optional[str] = None):
        from academic_pe.core.secrets import get_secret
        key = api_key or get_secret("openai")
        if not key:
            raise ValueError(
                "OpenAI API key is not configured. "
                "Please configure it in settings or set the OPENAI_API_KEY environment variable."
            )
        self._client = _get_openai_client(key)

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
        on_delta: Optional[StreamCallback] = None,
        reasoning_effort: Optional[str] = None,
    ) -> str:
        return _openai_chat_generate(self._client, system_prompt, user_prompt, model, temperature, on_delta, reasoning_effort)


class CustomOpenAIProvider(LLMProvider):
    def __init__(self, base_url: str, api_key: Optional[str] = None, api_key_env: str = "CUSTOM_API_KEY"):
        from academic_pe.core.secrets import get_secret
        key = api_key or get_secret("custom_openai") or os.getenv(api_key_env) or "sk-placeholder"
        self._client = _get_openai_client(key, base_url)

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
        on_delta: Optional[StreamCallback] = None,
        reasoning_effort: Optional[str] = None,
    ) -> str:
        return _openai_chat_generate(self._client, system_prompt, user_prompt, model, temperature, on_delta, reasoning_effort)


class GoogleProvider(LLMProvider):
    def __init__(self, api_key: Optional[str] = None):
        from academic_pe.core.secrets import get_secret
        key = api_key or get_secret("google")
        if not key:
            raise ValueError(
                "Google Gemini API key is not configured. "
                "Please configure it in settings or set the GEMINI_API_KEY/GOOGLE_API_KEY environment variable."
            )
        self._client = _get_openai_client(key, "https://generativelanguage.googleapis.com/v1beta/openai/")

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
        on_delta: Optional[StreamCallback] = None,
        reasoning_effort: Optional[str] = None,
    ) -> str:
        model_name = model
        if not model_name.startswith("gemini-"):
            model_name = "gemini-1.5-flash"
        return _openai_chat_generate(self._client, system_prompt, user_prompt, model_name, temperature, on_delta, reasoning_effort)


class LMStudioProvider(LLMProvider):
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        from academic_pe.core.secrets import get_secret
        url = base_url or "http://localhost:1234/v1"
        key = api_key or get_secret("lm_studio") or "lm-studio"
        self._client = _get_openai_client(key, url)

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
        on_delta: Optional[StreamCallback] = None,
        reasoning_effort: Optional[str] = None,
    ) -> str:
        return _openai_chat_generate(self._client, system_prompt, user_prompt, model, temperature, on_delta, reasoning_effort)


class ZenProvider(LLMProvider):
    def __init__(self, api_key: Optional[str] = None):
        from academic_pe.core.secrets import get_secret
        key = api_key or get_secret("zen")
        if not key:
            raise ValueError(
                "OpenCode Zen API key is not configured. "
                "Please configure it in settings or set the ZEN_API_KEY environment variable."
            )
        self._client = _get_openai_client(key, "https://opencode.ai/zen/v1")

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
        on_delta: Optional[StreamCallback] = None,
        reasoning_effort: Optional[str] = None,
    ) -> str:
        return _openai_chat_generate(self._client, system_prompt, user_prompt, model, temperature, on_delta, reasoning_effort)


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: Optional[str] = None):
        from academic_pe.core.secrets import get_secret
        key = api_key or get_secret("anthropic")
        if not key:
            raise ValueError(
                "Anthropic API key is not configured. "
                "Please configure it in settings or set the ANTHROPIC_API_KEY environment variable."
            )
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError(
                "anthropic package is required for AnthropicProvider. "
                "Install it with: pip install anthropic"
            )
        self._client = Anthropic(api_key=key)

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
        on_delta: Optional[StreamCallback] = None,
        reasoning_effort: Optional[str] = None,
    ) -> str:
        message = self._client.messages.create(
            model=model,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            temperature=temperature,
            max_tokens=4096,
        )
        if message.content:
            first_block = message.content[0]
            if hasattr(first_block, "text"):
                text = getattr(first_block, "text") or ""
                if on_delta is not None and text:
                    on_delta(text)
                return text
        return ""


class MockProvider(LLMProvider):
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
        on_delta: Optional[StreamCallback] = None,
        reasoning_effort: Optional[str] = None,
    ) -> str:
        text = (
            f"# Generated Section\n\n"
            f"This is a mock response for prompt: {user_prompt[:60]}...\n\n"
            f"System prompt used: {system_prompt[:60]}...\n"
            f"Model: {model}, Temperature: {temperature}"
        )
        if on_delta is not None:
            for chunk in text.split(" "):
                on_delta(f"{chunk} ")
        return text


@dataclass
class RetryConfig:
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0


class RetryProvider(LLMProvider):
    def __init__(self, inner: LLMProvider, config: RetryConfig = RetryConfig()):
        self._inner = inner
        self._config = config

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
        on_delta: Optional[StreamCallback] = None,
        reasoning_effort: Optional[str] = None,
    ) -> str:
        if self._config.max_retries <= 0:
            return _call_provider_generate(self._inner, system_prompt, user_prompt, model, temperature, on_delta, reasoning_effort)

        last_error: Optional[Exception] = None

        for attempt in range(self._config.max_retries):
            try:
                return _call_provider_generate(self._inner, system_prompt, user_prompt, model, temperature, on_delta, reasoning_effort)
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

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
        on_delta: Optional[StreamCallback] = None,
        reasoning_effort: Optional[str] = None,
    ) -> str:
        current_state = self.state
        if current_state == CircuitState.OPEN:
            raise RuntimeError(
                f"Circuit breaker is OPEN. "
                f"Retry after {self._config.recovery_timeout}s."
            )

        try:
            result = _call_provider_generate(self._inner, system_prompt, user_prompt, model, temperature, on_delta, reasoning_effort)
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
    "google": GoogleProvider,
    "lm_studio": LMStudioProvider,
    "zen": ZenProvider,
}


def register_provider(name: str, provider_cls: type[LLMProvider]) -> None:
    _PROVIDER_REGISTRY[name] = provider_cls


def create_provider(
    provider: str = "mock",
    base_url: Optional[str] = None,
    retry_config: Optional[RetryConfig] = None,
    circuit_breaker_config: Optional[Union[CircuitBreakerConfig, Any]] = None,
) -> LLMProvider:
    if provider == "custom_openai":
        if not base_url:
            raise ValueError("base_url is required for custom_openai provider")
        instance: LLMProvider = CustomOpenAIProvider(base_url=base_url)
    elif provider == "lm_studio":
        instance = LMStudioProvider(base_url=base_url)
    else:
        cls = _PROVIDER_REGISTRY.get(provider)
        if cls is None:
            raise ValueError(
                f"Unknown provider: {provider}. "
                f"Available: {list(_PROVIDER_REGISTRY)}"
            )
        instance = cls()

    if retry_config is not None and retry_config.max_retries > 0:
        instance = RetryProvider(instance, retry_config)

    if circuit_breaker_config is not None:
        enabled = getattr(circuit_breaker_config, "enabled", True)
        if enabled:
            instance = CircuitBreakerProvider(
                instance,
                CircuitBreakerConfig(
                    failure_threshold=circuit_breaker_config.failure_threshold,
                    recovery_timeout=circuit_breaker_config.recovery_timeout,
                ),
            )

    return instance
