from __future__ import annotations

from collections.abc import Callable, Iterable

from .models import (
    CredentialCandidate, CredentialSource, ProviderDefinition, ProviderHealth,
    RouteRequest, RoutingDecision,
)
from .registry import ProviderRegistry


class ProviderRoutingError(LookupError):
    pass


CredentialLookup = Callable[[RouteRequest, str], Iterable[CredentialCandidate]]
HealthLookup = Callable[[str], ProviderHealth]


class ProviderRouter:
    """Pure, deterministic selection policy. It returns references, never secrets."""

    def __init__(self, registry: ProviderRegistry, credentials: CredentialLookup,
                 health: HealthLookup | None = None) -> None:
        self.registry = registry
        self.credentials = credentials
        self.health = health or (lambda _provider: ProviderHealth.UNKNOWN)

    def route(self, request: RouteRequest) -> RoutingDecision:
        providers = self._ordered_providers(request)
        for fallback_index, provider in enumerate(providers):
            if self.health(provider.id) == ProviderHealth.OPEN:
                continue
            model = self._select_model(provider, request)
            if model is None:
                continue
            candidates = self._ordered_credentials(request, provider)
            if provider.requires_credential and not candidates:
                continue
            credential = candidates[0] if candidates else CredentialCandidate(
                provider.id, CredentialSource.NONE)
            return RoutingDecision(provider.id, model, credential.source,
                                   credential.credential_id, provider.base_url, fallback_index)
        raise ProviderRoutingError(f"no route for capability: {request.capability.value}")

    def _ordered_providers(self, request: RouteRequest) -> tuple[ProviderDefinition, ...]:
        preferred = {name: index for index, name in enumerate(request.preferred_providers)}
        available = self.registry.list()
        return tuple(sorted(available, key=lambda p: (
            0 if p.id in preferred else 1,
            preferred.get(p.id, 0),
            1 if self.health(p.id) == ProviderHealth.DEGRADED else 0,
            p.priority,
            p.id,
        )))

    @staticmethod
    def _select_model(provider: ProviderDefinition, request: RouteRequest) -> str | None:
        matches = [model for model in provider.models if request.capability in model.capabilities]
        if request.preferred_model:
            matches = [model for model in matches if model.id == request.preferred_model]
        return sorted((model.id for model in matches))[0] if matches else None

    def _ordered_credentials(self, request: RouteRequest,
                             provider: ProviderDefinition) -> list[CredentialCandidate]:
        allowed = set()
        if request.allow_user:
            allowed.add(CredentialSource.USER)
        if request.allow_platform:
            allowed.add(CredentialSource.PLATFORM)
        candidates = [candidate for candidate in self.credentials(request, provider.id)
                      if candidate.provider_id == provider.id and candidate.source in allowed]
        rank = {CredentialSource.USER: 0, CredentialSource.PLATFORM: 1, CredentialSource.NONE: 2}
        return sorted(candidates, key=lambda item: (rank[item.source], str(item.credential_id or "")))
