from __future__ import annotations

from enum import Enum
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field

from academic_pe.routing.cards import RetrievalCard, VectorRepresentation


class RoutingRetrievalPath(str, Enum):
    JINA_BM25 = "jina_bm25"
    E5_BM25 = "e5_bm25"
    BM25_LOCAL_RULES = "bm25_local_rules"
    LOCAL_RULES_ONLY = "local_rules_only"


class RoutingProviderReadiness(BaseModel):
    """Runtime readiness needed to select a retrieval path, not a confidence score."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    qdrant_healthy: bool = False
    jina_healthy: bool = False
    available_vectors: set[VectorRepresentation] = Field(default_factory=set)
    local_rules_available: bool = True

    @classmethod
    def from_cards(
        cls,
        cards: Iterable[RetrievalCard],
        *,
        qdrant_healthy: bool,
        jina_healthy: bool,
        local_rules_available: bool = True,
    ) -> "RoutingProviderReadiness":
        latest_by_scope: dict[tuple[str, str, object], RetrievalCard] = {}
        for card in cards:
            key = (card.entity_type.value, card.entity_id, card.tenant_id)
            previous = latest_by_scope.get(key)
            if previous is None or card.version > previous.version:
                latest_by_scope[key] = card
        active_cards = [card for card in latest_by_scope.values() if card.active]
        if not active_cards:
            available_vectors: set[VectorRepresentation] = set()
        else:
            available_vectors = {
                representation
                for representation in VectorRepresentation
                if all(card.vector_readiness[representation] for card in active_cards)
            }
        return cls(
            qdrant_healthy=qdrant_healthy,
            jina_healthy=jina_healthy,
            available_vectors=available_vectors,
            local_rules_available=local_rules_available,
        )


class RoutingFallbackChoice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    active_retrieval_path: RoutingRetrievalPath
    fallback_depth: int = Field(ge=0, le=3)
    planner_required: bool
    reasons: list[str] = Field(default_factory=list)


class RoutingFallbackPolicy:
    """Select the documented safe fallback path without performing I/O.

    Confidence remains a concern of ``RoutingDecision`` after candidate ranking;
    this policy only states which retrieval channels are actually available.
    """

    def select(self, readiness: RoutingProviderReadiness) -> RoutingFallbackChoice:
        vectors = readiness.available_vectors
        qdrant_ready = readiness.qdrant_healthy

        if (
            qdrant_ready
            and readiness.jina_healthy
            and VectorRepresentation.DENSE_JINA in vectors
            and VectorRepresentation.SPARSE_BM25 in vectors
        ):
            return RoutingFallbackChoice(
                active_retrieval_path=RoutingRetrievalPath.JINA_BM25,
                fallback_depth=0,
                planner_required=False,
                reasons=["Jina dense and Qdrant BM25 are ready"],
            )
        if (
            qdrant_ready
            and VectorRepresentation.DENSE_E5 in vectors
            and VectorRepresentation.SPARSE_BM25 in vectors
        ):
            return RoutingFallbackChoice(
                active_retrieval_path=RoutingRetrievalPath.E5_BM25,
                fallback_depth=1,
                planner_required=False,
                reasons=["Jina dense is unavailable; Qdrant E5 and BM25 are ready"],
            )
        if qdrant_ready and VectorRepresentation.SPARSE_BM25 in vectors:
            return RoutingFallbackChoice(
                active_retrieval_path=RoutingRetrievalPath.BM25_LOCAL_RULES,
                fallback_depth=2,
                planner_required=False,
                reasons=["Dense retrieval is unavailable; using Qdrant BM25 and local rules"],
            )
        if readiness.local_rules_available:
            return RoutingFallbackChoice(
                active_retrieval_path=RoutingRetrievalPath.LOCAL_RULES_ONLY,
                fallback_depth=3,
                planner_required=True,
                reasons=["Remote retrieval is unavailable; local rules require planner escalation"],
            )
        raise RuntimeError("no routing retrieval path is available")
