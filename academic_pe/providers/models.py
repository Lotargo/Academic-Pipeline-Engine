from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from uuid import UUID


class Capability(str, Enum):
    TEXT_GENERATION = "text_generation"
    VISION = "vision"
    EMBEDDINGS = "embeddings"
    OCR = "ocr"
    STREAMING = "streaming"
    TOOLS = "tools"


class CredentialSource(str, Enum):
    USER = "user"
    PLATFORM = "platform"
    NONE = "none"


class ProviderHealth(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    OPEN = "open"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ModelMetadata:
    id: str
    capabilities: frozenset[Capability]
    context_window: int | None = None
    # Quotas are deliberately not represented here: unknown capacity must stay unknown.
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderDefinition:
    id: str
    models: tuple[ModelMetadata, ...]
    display_name: str | None = None
    openai_compatible: bool = False
    base_url: str | None = None
    requires_credential: bool = True
    priority: int = 100


@dataclass(frozen=True)
class CredentialCandidate:
    provider_id: str
    source: CredentialSource
    credential_id: UUID | None = None


@dataclass(frozen=True)
class RouteRequest:
    capability: Capability
    workspace_id: UUID
    preferred_providers: tuple[str, ...] = ()
    preferred_model: str | None = None
    allow_platform: bool = True
    allow_user: bool = True


@dataclass(frozen=True)
class RoutingDecision:
    provider_id: str
    model_id: str
    credential_source: CredentialSource
    credential_id: UUID | None
    base_url: str | None = None
    fallback_index: int = 0
