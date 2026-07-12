from __future__ import annotations

from dataclasses import dataclass

from academic_pe.instructions.skills import SkillRegistry
from academic_pe.manifests.loader import ArtifactManifestLoader
from academic_pe.routing.cards import (
    RetrievalCard,
    VectorRepresentation,
    artifact_retrieval_cards,
    skill_retrieval_cards,
)
from academic_pe.routing.config import ProviderInfrastructureConfig
from academic_pe.routing.qdrant import QdrantRoutingIndex, QdrantRoutingRecord


@dataclass(frozen=True)
class RoutingProjectionReport:
    collection_name: str
    indexed_card_count: int
    collection_created: bool


def canonical_routing_cards() -> list[RetrievalCard]:
    """Create the Qdrant projection from canonical manifests, never vice versa."""

    artifacts = ArtifactManifestLoader("config/artifact_manifests.yaml").load()
    skills = SkillRegistry.from_yaml().manifests
    return [*artifact_retrieval_cards(artifacts.values()), *skill_retrieval_cards(skills)]


def cloud_inference_record(
    card: RetrievalCard,
    configuration: ProviderInfrastructureConfig,
) -> QdrantRoutingRecord:
    """Attach verified Cloud Inference documents to one canonical routing card."""

    settings = configuration.providers.qdrant
    if not settings.cloud_inference_enabled:
        raise ValueError("Qdrant Cloud Inference is disabled")
    models = {
        VectorRepresentation.DENSE_E5: settings.multilingual_dense_model_id,
        VectorRepresentation.SPARSE_BM25: settings.sparse_model_id,
        VectorRepresentation.LATE_COLBERT: settings.late_interaction_model_id,
    }
    missing = [representation.value for representation, model_id in models.items() if not model_id]
    if missing:
        raise ValueError(f"Qdrant routing model IDs are not configured: {', '.join(missing)}")
    ready_card = card.model_copy(update={
        "vector_readiness": {
            VectorRepresentation.DENSE_JINA: False,
            VectorRepresentation.DENSE_E5: True,
            VectorRepresentation.SPARSE_BM25: True,
            VectorRepresentation.LATE_COLBERT: True,
        },
    })
    return QdrantRoutingRecord(
        card=ready_card,
        vectors={
            representation: {"text": ready_card.embedding_text(), "model": model_id}
            for representation, model_id in models.items()
        },
    )


async def reindex_canonical_routing_cards(
    index: QdrantRoutingIndex,
    configuration: ProviderInfrastructureConfig,
) -> RoutingProjectionReport:
    """Idempotently provision and upsert every canonical routing card."""

    cards = canonical_routing_cards()
    created = await index.ensure_collection()
    await index.upsert_vector_records([
        cloud_inference_record(card, configuration)
        for card in cards
    ])
    return RoutingProjectionReport(
        collection_name=configuration.routing.collection_name,
        indexed_card_count=len(cards),
        collection_created=created,
    )
