from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Iterable
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from academic_pe.instructions.skills import SkillManifest

if TYPE_CHECKING:
    from academic_pe.manifests.models import ArtifactManifest


class RoutingEntityType(str, Enum):
    ARTIFACT = "artifact"
    TEMPLATE = "template"
    SKILL = "skill"


class VectorRepresentation(str, Enum):
    DENSE_JINA = "dense_jina"
    DENSE_E5 = "dense_e5"
    SPARSE_BM25 = "sparse_bm25"
    LATE_COLBERT = "late_colbert"


def _empty_readiness() -> dict[VectorRepresentation, bool]:
    return {representation: False for representation in VectorRepresentation}


class RetrievalCard(BaseModel):
    """Versioned routing projection; canonical manifests remain source of truth."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_type: RoutingEntityType
    entity_id: str = Field(..., min_length=1)
    version: int = Field(ge=1)
    title: str = Field(..., min_length=1)
    descriptions: dict[str, list[str]]
    positive_examples: list[str] = Field(default_factory=list)
    negative_examples: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    compatible_artifacts: list[str] = Field(default_factory=list)
    agent_scope: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    tenant_id: UUID | None = None
    active: bool = True
    vector_readiness: dict[VectorRepresentation, bool] = Field(default_factory=_empty_readiness)

    @model_validator(mode="after")
    def validate_descriptions_and_readiness(self) -> "RetrievalCard":
        if not any(item.strip() for values in self.descriptions.values() for item in values):
            raise ValueError("retrieval card requires at least one description")
        missing = set(VectorRepresentation).difference(self.vector_readiness)
        if missing:
            raise ValueError("vector_readiness must declare every named representation")
        return self

    @property
    def card_key(self) -> str:
        tenant = str(self.tenant_id) if self.tenant_id else "global"
        return f"{tenant}:{self.entity_type.value}:{self.entity_id}:v{self.version}"

    def embedding_text(self) -> str:
        """Positive projection only; negative examples belong to the penalty layer."""

        parts = [self.title]
        for language in sorted(self.descriptions):
            parts.extend(self.descriptions[language])
        parts.extend(self.positive_examples)
        parts.extend(self.capabilities)
        return "\n".join(dict.fromkeys(item.strip() for item in parts if item.strip()))

    def negative_text(self) -> str:
        return "\n".join(dict.fromkeys(item.strip() for item in self.negative_examples if item.strip()))


def artifact_retrieval_cards(manifests: Iterable["ArtifactManifest"]) -> list[RetrievalCard]:
    cards: list[RetrievalCard] = []
    for manifest in manifests:
        profile = manifest.retrieval
        descriptions = (
            {language: list(values) for language, values in profile.descriptions.items()}
            if profile
            else {}
        )
        if manifest.description:
            descriptions.setdefault("en", [])
            if manifest.description not in descriptions["en"]:
                descriptions["en"].append(manifest.description)
        if not descriptions:
            descriptions = {"en": [manifest.id.replace("_", " ")]}
        cards.append(RetrievalCard(
            entity_type=RoutingEntityType.ARTIFACT,
            entity_id=manifest.id,
            version=manifest.version,
            title=profile.title if profile else manifest.id.replace("_", " ").title(),
            descriptions=descriptions,
            positive_examples=list(profile.positive_examples) if profile else [],
            negative_examples=list(profile.negative_examples) if profile else [],
            capabilities=list(profile.capabilities) if profile else [],
            compatible_artifacts=[manifest.id],
            agent_scope=list(profile.agent_scope) if profile else [],
        ))
    return cards


def skill_retrieval_cards(manifests: Iterable[SkillManifest]) -> list[RetrievalCard]:
    cards: list[RetrievalCard] = []
    for manifest in manifests:
        descriptions = {language: list(values) for language, values in manifest.descriptions.items()}
        descriptions.setdefault("en", [])
        if manifest.description not in descriptions["en"]:
            descriptions["en"].append(manifest.description)
        cards.append(RetrievalCard(
            entity_type=RoutingEntityType.SKILL,
            entity_id=manifest.skill_id,
            version=manifest.version,
            title=manifest.skill_id.replace("_", " ").title(),
            descriptions=descriptions,
            positive_examples=list(manifest.positive_examples),
            negative_examples=list(manifest.negative_examples),
            capabilities=list(manifest.provides),
            compatible_artifacts=list(manifest.compatible_artifacts),
            agent_scope=[role.value for role in manifest.agent_scope],
            dependencies=list(manifest.requires),
            conflicts=list(manifest.conflicts_with),
        ))
    return cards
