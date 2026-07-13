from __future__ import annotations

from collections.abc import Callable, Iterable
from uuid import UUID

from academic_pe.observability.events import ObservabilityEvent
from academic_pe.observability.runtime import get_correlation_id

from .models import (
    CredentialCandidate, CredentialPolicy, CredentialSource, ProviderDefinition, ProviderHealth,
    RouteRequest, RoutingDecision,
)
from .registry import ProviderRegistry


class ProviderRoutingError(LookupError):
    pass


CredentialLookup = Callable[[RouteRequest, str], Iterable[CredentialCandidate]]
HealthLookup = Callable[[str], ProviderHealth]
EventRecorder = Callable[[ObservabilityEvent], None]


class ProviderRouter:
    """Pure, deterministic selection policy. It returns references, never secrets."""

    def __init__(self, registry: ProviderRegistry, credentials: CredentialLookup,
                 health: HealthLookup | None = None, *, event_recorder: EventRecorder | None = None) -> None:
        self.registry = registry
        self.credentials = credentials
        self.health = health or (lambda _provider: ProviderHealth.UNKNOWN)
        self.event_recorder = event_recorder

    def route(self, request: RouteRequest) -> RoutingDecision:
        providers = self._ordered_providers(request)
        for fallback_index, provider in enumerate(providers):
            if self.health(provider.id) == ProviderHealth.OPEN:
                self._record(
                    "provider.routing.unavailable", "warning", "circuit_open", request.workspace_id,
                    {"provider_id": provider.id, "fallback_index": fallback_index},
                )
                continue
            model = self._select_model(provider, request)
            if model is None:
                continue
            candidates = self._ordered_credentials(request, provider)
            if provider.requires_credential and not candidates:
                continue
            credential = candidates[0] if candidates else CredentialCandidate(
                provider.id, CredentialSource.NONE)
            decision = RoutingDecision(provider.id, model, credential.source,
                                       credential.credential_id, provider.base_url, fallback_index)
            if fallback_index:
                self._record(
                    "provider.routing.fallback", "warning", "selected_after_fallback", request.workspace_id,
                    {"provider_id": provider.id, "fallback_index": fallback_index},
                )
            return decision
        self._record(
            "provider.routing.failed", "error", "no_route", request.workspace_id,
            {"capability": request.capability.value, "provider_count": len(providers)},
        )
        raise ProviderRoutingError(f"no route for capability: {request.capability.value}")

    def _record(self, event_type: str, severity: str, outcome: str, workspace_id: UUID,
                details: dict[str, object]) -> None:
        if self.event_recorder is None:
            return
        try:
            self.event_recorder(ObservabilityEvent(
                event_type=event_type,
                severity=severity,  # type: ignore[arg-type]
                correlation_id=get_correlation_id() or "service_00000000",
                source="provider_router",
                outcome=outcome,
                workspace_id=str(workspace_id),
                details=details,
            ))
        except Exception:
            # Routing remains available if a local telemetry adapter is unavailable.
            return

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
        if request.allow_user and request.credential_policy != CredentialPolicy.PLATFORM_ONLY:
            allowed.add(CredentialSource.USER)
        if request.allow_platform and request.credential_policy != CredentialPolicy.USER_ONLY:
            allowed.add(CredentialSource.PLATFORM)
        candidates = [candidate for candidate in self.credentials(request, provider.id)
                      if candidate.provider_id == provider.id and candidate.source in allowed]
        platform_first = request.credential_policy in {
            CredentialPolicy.PLATFORM_FIRST, CredentialPolicy.PLATFORM_ONLY}
        rank = ({CredentialSource.PLATFORM: 0, CredentialSource.USER: 1, CredentialSource.NONE: 2}
                if platform_first else
                {CredentialSource.USER: 0, CredentialSource.PLATFORM: 1, CredentialSource.NONE: 2})
        return sorted(candidates, key=lambda item: (rank[item.source], str(item.credential_id or "")))
