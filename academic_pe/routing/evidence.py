from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class RoutingEvidenceChannel(str, Enum):
    """A retrieval or deterministic scoring channel represented in routing output."""

    LEXICAL_RULES = "lexical_rules"
    QDRANT_E5 = "qdrant_e5"
    QDRANT_BM25 = "qdrant_bm25"
    RRF = "rrf"
    COLBERT = "colbert"
    GRAPH_PENALTY = "graph_penalty"


class RoutingChannelEvidence(BaseModel):
    """Observable contribution from one routing channel for one candidate.

    ``raw_score`` intentionally remains unconstrained: cosine, BM25 and
    ColBERT scores each use their own scale.  Downstream routing uses only
    rank-based fusion; ``contribution`` is the normalized value actually used
    by APE after fusion or a negative deterministic penalty.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    channel: RoutingEvidenceChannel
    raw_score: float
    contribution: float = Field(ge=-1.0, le=1.0)
    rank: int | None = Field(default=None, ge=1)
    details: list[str] = Field(default_factory=list)
