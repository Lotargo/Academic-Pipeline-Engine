from __future__ import annotations

from typing import Protocol

from .models import ProviderDefinition


class ProviderAdapter(Protocol):
    """Provider-specific boundary; domain code only consumes the generic adapter."""

    provider_id: str

    def validate_model(self, model_id: str) -> bool: ...


class ProviderRegistry(Protocol):
    def get(self, provider_id: str) -> ProviderDefinition | None: ...
    def list(self) -> tuple[ProviderDefinition, ...]: ...
    def adapter(self, provider_id: str) -> ProviderAdapter | None: ...


class InMemoryProviderRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, ProviderDefinition] = {}
        self._adapters: dict[str, ProviderAdapter] = {}

    def register(self, definition: ProviderDefinition, adapter: ProviderAdapter | None = None) -> None:
        if not definition.id.strip():
            raise ValueError("provider id must not be empty")
        if definition.id in self._definitions:
            raise ValueError(f"provider already registered: {definition.id}")
        if not definition.models:
            raise ValueError("provider must define at least one model")
        self._definitions[definition.id] = definition
        if adapter is not None:
            if adapter.provider_id != definition.id:
                raise ValueError("adapter provider_id does not match definition")
            self._adapters[definition.id] = adapter

    def get(self, provider_id: str) -> ProviderDefinition | None:
        return self._definitions.get(provider_id)

    def list(self) -> tuple[ProviderDefinition, ...]:
        return tuple(sorted(self._definitions.values(), key=lambda item: (item.priority, item.id)))

    def adapter(self, provider_id: str) -> ProviderAdapter | None:
        return self._adapters.get(provider_id)
