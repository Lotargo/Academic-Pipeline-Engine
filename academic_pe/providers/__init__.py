"""Tenant-aware provider registry and deterministic routing."""

from .models import (
    Capability,
    CredentialCandidate,
    CredentialSource,
    ModelMetadata,
    ProviderDefinition,
    ProviderHealth,
    RouteRequest,
    RoutingDecision,
)
from .registry import InMemoryProviderRegistry, ProviderAdapter, ProviderRegistry
from .router import ProviderRoutingError, ProviderRouter

__all__ = [
    "Capability", "CredentialCandidate", "CredentialSource", "ModelMetadata",
    "ProviderDefinition", "ProviderHealth", "RouteRequest", "RoutingDecision",
    "InMemoryProviderRegistry", "ProviderAdapter", "ProviderRegistry",
    "ProviderRoutingError", "ProviderRouter",
]
