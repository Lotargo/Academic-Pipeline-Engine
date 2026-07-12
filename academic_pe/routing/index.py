from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from academic_pe.routing.cards import RetrievalCard, RoutingEntityType
from academic_pe.routing.evidence import RoutingChannelEvidence, RoutingEvidenceChannel


_TOKEN_RE = re.compile(r"[^\W_]+", flags=re.UNICODE)


class RoutingQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., min_length=1)
    entity_types: set[RoutingEntityType] = Field(default_factory=set)
    artifact_id: str | None = None
    agent_role: str | None = None
    tenant_id: UUID | None = None
    include_inactive: bool = False
    top_k: int = Field(default=10, ge=1, le=100)
    available_capabilities: set[str] = Field(default_factory=set)
    selected_skill_ids: set[str] = Field(default_factory=set)


class RoutingSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    card: RetrievalCard
    score: float = Field(ge=0.0, le=1.0)
    matched_terms: list[str] = Field(default_factory=list)
    matched_positive_examples: list[str] = Field(default_factory=list)
    matched_negative_examples: list[str] = Field(default_factory=list)
    channel_evidence: list[RoutingChannelEvidence] = Field(default_factory=list)


class RoutingIndexHealth(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    healthy: bool
    adapter: str
    record_count: int = Field(ge=0)
    details: list[str] = Field(default_factory=list)


@runtime_checkable
class RoutingIndex(Protocol):
    async def upsert(self, records: Sequence[RetrievalCard]) -> None: ...

    async def delete(
        self,
        entity_id: str,
        version: int,
        *,
        entity_type: RoutingEntityType,
        tenant_id: UUID | None = None,
    ) -> None: ...

    async def search(self, query: RoutingQuery) -> list[RoutingSearchResult]: ...

    async def healthcheck(self) -> RoutingIndexHealth: ...


class InMemoryRoutingIndex:
    """Deterministic local adapter used when no retrieval service is available."""

    def __init__(self) -> None:
        self._records: dict[tuple[RoutingEntityType, str, int, UUID | None], RetrievalCard] = {}

    async def upsert(self, records: Sequence[RetrievalCard]) -> None:
        for record in records:
            key = (record.entity_type, record.entity_id, record.version, record.tenant_id)
            self._records[key] = record

    async def delete(
        self,
        entity_id: str,
        version: int,
        *,
        entity_type: RoutingEntityType,
        tenant_id: UUID | None = None,
    ) -> None:
        keys = [
            key
            for key in self._records
            if key[1] == entity_id
            and key[2] == version
            and key[0] is entity_type
            and key[3] == tenant_id
        ]
        for key in keys:
            self._records.pop(key, None)

    async def search(self, query: RoutingQuery) -> list[RoutingSearchResult]:
        results: list[RoutingSearchResult] = []
        for card in self._latest_visible_records(query):
            result = _score_card(query, card)
            if result.score > 0:
                results.append(result)
        results.sort(key=lambda item: (-item.score, item.card.entity_type.value, item.card.entity_id))
        return results[:query.top_k]

    async def healthcheck(self) -> RoutingIndexHealth:
        return RoutingIndexHealth(
            healthy=True,
            adapter="in_memory",
            record_count=len(self._records),
        )

    def _latest_visible_records(self, query: RoutingQuery) -> list[RetrievalCard]:
        return visible_routing_cards(self._records.values(), query)


def visible_routing_cards(records: Sequence[RetrievalCard], query: RoutingQuery) -> list[RetrievalCard]:
    """Apply canonical version, active, scope and graph visibility rules."""

    latest: dict[tuple[RoutingEntityType, str], RetrievalCard] = {}
    for card in records:
        if query.entity_types and card.entity_type not in query.entity_types:
            continue
        if query.tenant_id is None and card.tenant_id is not None:
            continue
        if query.tenant_id is not None and card.tenant_id not in {None, query.tenant_id}:
            continue
        key = (card.entity_type, card.entity_id)
        previous = latest.get(key)
        card_is_tenant_override = query.tenant_id is not None and card.tenant_id == query.tenant_id
        previous_is_tenant_override = (
            previous is not None
            and query.tenant_id is not None
            and previous.tenant_id == query.tenant_id
        )
        if previous is None:
            latest[key] = card
        elif card_is_tenant_override and not previous_is_tenant_override:
            latest[key] = card
        elif card_is_tenant_override == previous_is_tenant_override and card.version > previous.version:
            latest[key] = card

    visible: list[RetrievalCard] = []
    for card in latest.values():
        if not query.include_inactive and not card.active:
            continue
        if query.artifact_id:
            if card.entity_type is RoutingEntityType.ARTIFACT and card.entity_id != query.artifact_id:
                continue
            if card.entity_type is not RoutingEntityType.ARTIFACT and card.compatible_artifacts:
                if query.artifact_id not in card.compatible_artifacts:
                    continue
        if query.agent_role and card.agent_scope and query.agent_role not in card.agent_scope:
            continue
        visible.append(card)
    return visible


def _score_card(query: RoutingQuery, card: RetrievalCard) -> RoutingSearchResult:
    query_text = query.text
    query_tokens = _tokens(query_text)
    searchable_tokens = _tokens(card.embedding_text())
    matched_terms = sorted(query_tokens.intersection(searchable_tokens))
    positive = _matched_phrases(query_text, card.positive_examples)
    negative = _matched_phrases(query_text, card.negative_examples)

    overlap = len(matched_terms) / max(1, len(query_tokens))
    identity_bonus = 0.0
    normalized_query = query_text.casefold()
    if card.entity_id.replace("_", " ").casefold() in normalized_query:
        identity_bonus = 0.25
    elif card.title.casefold() in normalized_query:
        identity_bonus = 0.20
    positive_bonus = min(0.25, 0.10 * len(positive))
    lexical_score = min(1.0, (0.65 * overlap) + identity_bonus + positive_bonus)
    return scored_routing_result(
        query=query,
        card=card,
        base_score=lexical_score,
        channel_evidence=[RoutingChannelEvidence(
            channel=RoutingEvidenceChannel.LEXICAL_RULES,
            raw_score=round(lexical_score, 6),
            contribution=round(lexical_score, 6),
            details=[f"{len(matched_terms)} lexical term(s)", *positive],
        )],
        matched_terms=matched_terms,
        matched_positive_examples=positive,
        matched_negative_examples=negative,
    )


def scored_routing_result(
    *,
    query: RoutingQuery,
    card: RetrievalCard,
    base_score: float,
    channel_evidence: Sequence[RoutingChannelEvidence],
    matched_terms: Sequence[str] | None = None,
    matched_positive_examples: Sequence[str] | None = None,
    matched_negative_examples: Sequence[str] | None = None,
) -> RoutingSearchResult:
    """Apply negative examples and typed-graph penalties after rank fusion."""

    terms = list(matched_terms if matched_terms is not None else _tokens(query.text).intersection(_tokens(card.embedding_text())))
    positive = list(matched_positive_examples if matched_positive_examples is not None else _matched_phrases(query.text, card.positive_examples))
    negative = list(matched_negative_examples if matched_negative_examples is not None else _matched_phrases(query.text, card.negative_examples))
    negative_penalty = min(0.75, 0.35 * len(negative))
    missing_dependencies = sorted(set(card.dependencies).difference(query.available_capabilities))
    conflicting_skills = sorted(set(card.conflicts).intersection(query.selected_skill_ids))
    graph_penalty = min(0.75, 0.15 * len(missing_dependencies) + 0.60 * len(conflicting_skills))
    penalty = min(0.95, negative_penalty + graph_penalty)
    evidence = list(channel_evidence)
    if penalty:
        details = [
            *([f"negative examples: {', '.join(negative)}"] if negative else []),
            *([f"missing capabilities: {', '.join(missing_dependencies)}"] if missing_dependencies else []),
            *([f"conflicting skills: {', '.join(conflicting_skills)}"] if conflicting_skills else []),
        ]
        evidence.append(RoutingChannelEvidence(
            channel=RoutingEvidenceChannel.GRAPH_PENALTY,
            raw_score=round(penalty, 6),
            contribution=round(-penalty, 6),
            details=details,
        ))
    score = max(0.0, min(1.0, base_score - penalty))
    return RoutingSearchResult(
        card=card,
        score=round(score, 6),
        matched_terms=sorted(terms),
        matched_positive_examples=positive,
        matched_negative_examples=negative,
        channel_evidence=evidence,
    )


def _tokens(value: str) -> set[str]:
    # One-character function words (for example Russian "в") must not win a
    # lexical tie against an artifact-specific cue.
    return {
        token.casefold()
        for match in _TOKEN_RE.finditer(value)
        if len(token := match.group(0)) > 1
    }


def _matched_phrases(query_text: str, phrases: Sequence[str]) -> list[str]:
    normalized = query_text.casefold()
    query_tokens = _tokens(query_text)
    matched: list[str] = []
    for phrase in phrases:
        phrase_tokens = _tokens(phrase)
        if phrase.casefold() in normalized or (phrase_tokens and phrase_tokens.issubset(query_tokens)):
            matched.append(phrase)
    return matched
