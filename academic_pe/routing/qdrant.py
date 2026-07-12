from __future__ import annotations

import json
from asyncio import gather
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

import httpx

from academic_pe.core.secrets import SecretResolver
from academic_pe.routing.cards import RetrievalCard, RoutingEntityType, VectorRepresentation
from academic_pe.routing.config import ProviderInfrastructureConfig
from academic_pe.routing.evidence import RoutingChannelEvidence, RoutingEvidenceChannel
from academic_pe.routing.fallback import RoutingFallbackPolicy, RoutingProviderReadiness, RoutingRetrievalPath
from academic_pe.routing.index import (
    InMemoryRoutingIndex,
    RoutingIndex,
    RoutingIndexHealth,
    RoutingQuery,
    RoutingSearchResult,
    _matched_phrases,
    _tokens,
    scored_routing_result,
    visible_routing_cards,
)


class QdrantRoutingIndexError(RuntimeError):
    """A non-retryable Qdrant request or projection error."""


class QdrantRoutingIndexUnavailable(QdrantRoutingIndexError):
    """A temporary Qdrant failure for which the local fallback is safe."""


@dataclass(frozen=True)
class QdrantCollectionSchema:
    """Named-vector schema for the routing projection collection."""

    dense_e5_size: int = 384
    late_colbert_size: int = 96

    def __post_init__(self) -> None:
        if self.dense_e5_size < 1 or self.late_colbert_size < 1:
            raise ValueError("Qdrant named-vector sizes must be positive")

    def collection_payload(self) -> dict[str, Any]:
        return {
            "vectors": {
                VectorRepresentation.DENSE_E5.value: {
                    "size": self.dense_e5_size,
                    "distance": "Cosine",
                },
                VectorRepresentation.LATE_COLBERT.value: {
                    "size": self.late_colbert_size,
                    "distance": "Cosine",
                    "multivector_config": {"comparator": "max_sim"},
                    "hnsw_config": {"m": 0},
                },
            },
            "sparse_vectors": {VectorRepresentation.SPARSE_BM25.value: {}},
        }


@dataclass(frozen=True)
class QdrantRoutingRecord:
    """A routing card plus precomputed named vectors ready for Qdrant upload.

    The adapter never guesses model IDs or produces embeddings itself.  Callers
    must supply representations only after the matching provider/model has been
    configured and validated.
    """

    card: RetrievalCard
    vectors: Mapping[VectorRepresentation, Any]

    def to_point(self) -> dict[str, Any]:
        actual = {VectorRepresentation(name) for name in self.vectors}
        expected = {
            representation
            for representation, ready in self.card.vector_readiness.items()
            if ready
        }


        if actual != expected:
            raise ValueError(
                "vector_readiness must exactly match vectors supplied to QdrantRoutingRecord"
            )
        serialized_vectors = {representation.value: self.vectors[representation] for representation in actual}
        try:
            json.dumps(serialized_vectors)
        except (TypeError, ValueError) as exc:
            raise ValueError("Qdrant vectors must be JSON serializable") from exc
        return {
            "id": _point_id(self.card),
            "vector": serialized_vectors,
            "payload": _payload(self.card),
        }


@dataclass(frozen=True)
class _QdrantChannelHit:
    card: RetrievalCard
    point_id: str
    scope: str
    channel: RoutingEvidenceChannel
    raw_score: float
    rank: int


class QdrantRoutingIndex:
    """Optional Qdrant projection with a deterministic local-safe fallback.

    Cloud vectors are a retrieval projection, never the source of truth.  The
    adapter first enforces local version/tenant visibility rules, then queries
    only the active global and caller tenant scopes.  E5 and BM25 are fused by
    rank rather than by their incomparable raw scores; ColBERT receives only
    the resulting top candidates as a second-stage reranker.
    """

    def __init__(
        self,
        *,
        url: str,
        collection_name: str,
        api_key: str | None = None,
        timeout_seconds: int = 15,
        max_scroll_pages: int = 8,
        collection_schema: QdrantCollectionSchema | None = None,
        cloud_inference_enabled: bool = False,
        e5_model_id: str | None = None,
        bm25_model_id: str | None = None,
        colbert_model_id: str | None = None,
        candidate_top_k: int = 20,
        rerank_top_k: int = 8,
        rrf_k: int = 60,
        fallback_index: RoutingIndex | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        normalized_url = url.strip().rstrip("/")
        if not normalized_url:
            raise ValueError("Qdrant URL must not be empty")
        if not collection_name.strip():
            raise ValueError("Qdrant collection name must not be empty")
        if timeout_seconds < 1:
            raise ValueError("timeout_seconds must be at least one second")
        if max_scroll_pages < 1:
            raise ValueError("max_scroll_pages must be at least one")
        if candidate_top_k < 1 or rerank_top_k < 1:
            raise ValueError("routing candidate and rerank limits must be positive")
        if rerank_top_k > candidate_top_k:
            raise ValueError("rerank_top_k cannot exceed candidate_top_k")
        if rrf_k < 1:
            raise ValueError("rrf_k must be positive")

        self._url = normalized_url
        self._collection_name = collection_name
        self._api_key = api_key.strip() if api_key and api_key.strip() else None
        self._timeout_seconds = timeout_seconds
        self._max_scroll_pages = max_scroll_pages
        self._collection_schema = collection_schema or QdrantCollectionSchema()
        self._cloud_inference_enabled = cloud_inference_enabled
        self._e5_model_id = _clean_model_id(e5_model_id)
        self._bm25_model_id = _clean_model_id(bm25_model_id)
        self._colbert_model_id = _clean_model_id(colbert_model_id)
        self._candidate_top_k = candidate_top_k
        self._rerank_top_k = rerank_top_k
        self._rrf_k = rrf_k
        self._fallback_index = fallback_index
        self._transport = transport
        self._client: httpx.AsyncClient | None = None

    @classmethod
    def from_provider_config(
        cls,
        configuration: ProviderInfrastructureConfig,
        *,
        secret_resolver: SecretResolver | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> "QdrantRoutingIndex":
        settings = configuration.providers.qdrant
        if not settings.url:
            raise ValueError("Qdrant URL is not configured")
        api_key = (secret_resolver or SecretResolver()).resolve("QDRANT_API_KEY")
        if not api_key:
            raise ValueError("Qdrant API key is not configured")
        return cls(
            url=settings.url,
            collection_name=configuration.routing.collection_name,
            api_key=api_key,
            timeout_seconds=configuration.routing.timeout_seconds,
            collection_schema=QdrantCollectionSchema(
                dense_e5_size=settings.multilingual_dense_vector_size,
                late_colbert_size=settings.late_interaction_vector_size,
            ),
            cloud_inference_enabled=settings.cloud_inference_enabled,
            e5_model_id=settings.multilingual_dense_model_id,
            bm25_model_id=settings.sparse_model_id,
            colbert_model_id=settings.late_interaction_model_id,
            candidate_top_k=configuration.routing.candidate_top_k,
            rerank_top_k=configuration.routing.rerank_top_k,
            transport=transport,
        )

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def ensure_collection(self) -> bool:
        """Create the named-vector collection and filter indexes when absent.

        The operation is idempotent: an existing collection is preserved and
        only the required payload indexes are asserted.
        """

        response = await self._request_response("GET", f"/collections/{self._collection_name}")
        created = False
        if response.status_code == 404:
            await self._request(
                "PUT",
                f"/collections/{self._collection_name}",
                json=self._collection_schema.collection_payload(),
            )
            created = True
        else:
            self._raise_for_error(response)
            self._validate_existing_schema(response)
        for field_name, field_schema in (
            ("scope", "keyword"),
            ("entity_type", "keyword"),
            ("entity_id", "keyword"),
            ("active", "bool"),
        ):
            await self._request(
                "PUT",
                f"/collections/{self._collection_name}/index",
                json={"field_name": field_name, "field_schema": field_schema},
            )
        return created

    async def upsert(self, records: Sequence[RetrievalCard]) -> None:
        for card in records:
            if any(card.vector_readiness.values()):
                raise ValueError(
                    "use upsert_vector_records when a card has ready named vectors"
                )
        points = [{"id": _point_id(card), "payload": _payload(card)} for card in records]
        if points:
            await self._upsert_points(points)

    async def upsert_vector_records(self, records: Sequence[QdrantRoutingRecord]) -> None:
        points = [record.to_point() for record in records]
        if points:
            await self._upsert_points(points)

    async def delete(
        self,
        entity_id: str,
        version: int,
        *,
        entity_type: RoutingEntityType,
        tenant_id: UUID | None = None,
    ) -> None:
        card_key = _card_key(entity_type, entity_id, version, tenant_id)
        await self._request(
            "POST",
            f"/collections/{self._collection_name}/points/delete",
            params={"wait": "true"},
            json={"points": [str(uuid5(NAMESPACE_URL, f"academic-pipeline-engine:routing:{card_key}"))]},
        )

    async def search(self, query: RoutingQuery) -> list[RoutingSearchResult]:
        try:
            cards: list[RetrievalCard] = []
            for scope in _visible_scopes(query.tenant_id):
                cards.extend(await self._scroll_scope(scope, query))
        except QdrantRoutingIndexUnavailable as exc:
            return await self._fallback_or_raise(query, exc)

        local_projection = InMemoryRoutingIndex()
        await local_projection.upsert(cards)
        visible_cards = visible_routing_cards(cards, query)
        if not visible_cards:
            return []

        choice = RoutingFallbackPolicy().select(RoutingProviderReadiness.from_cards(
            visible_cards,
            qdrant_healthy=self._semantic_query_enabled(),
            jina_healthy=False,
        ))
        if choice.active_retrieval_path is RoutingRetrievalPath.LOCAL_RULES_ONLY:
            return await local_projection.search(query)

        try:
            results = await self._semantic_search(
                query,
                visible_cards,
                use_e5=choice.active_retrieval_path is RoutingRetrievalPath.E5_BM25,
                use_colbert=choice.active_retrieval_path is RoutingRetrievalPath.E5_BM25,
            )
        except QdrantRoutingIndexUnavailable as exc:
            return await self._fallback_or_raise(query, exc)
        # A readiness mismatch can leave a projection without vector points.
        # Preserve the local path instead of making routing silently empty.
        return results or await local_projection.search(query)

    async def healthcheck(self) -> RoutingIndexHealth:
        try:
            payload = await self._request("GET", f"/collections/{self._collection_name}")
            result = payload.get("result") if isinstance(payload, dict) else None
            record_count = result.get("points_count", 0) if isinstance(result, dict) else 0
            return RoutingIndexHealth(
                healthy=True,
                adapter="qdrant",
                record_count=max(0, int(record_count or 0)),
                details=[f"collection={self._collection_name}"],
            )
        except QdrantRoutingIndexError as exc:
            return RoutingIndexHealth(
                healthy=False,
                adapter="qdrant",
                record_count=0,
                details=[str(exc)],
            )

    async def _upsert_points(self, points: list[dict[str, Any]]) -> None:
        await self._request(
            "PUT",
            f"/collections/{self._collection_name}/points",
            params={"wait": "true"},
            json={"points": points},
        )

    async def _scroll_scope(self, scope: str, query: RoutingQuery) -> list[RetrievalCard]:
        records: list[RetrievalCard] = []
        offset: str | int | None = None
        page_limit = min(256, max(64, query.top_k * 4))
        for _ in range(self._max_scroll_pages):
            body: dict[str, Any] = {
                "filter": _scope_filter(scope, query.entity_types),
                "limit": page_limit,
                "with_payload": True,
                "with_vector": False,
            }
            if offset is not None:
                body["offset"] = offset
            payload = await self._request(
                "POST",
                f"/collections/{self._collection_name}/points/scroll",
                json=body,
            )
            result = payload.get("result") if isinstance(payload, dict) else None
            if not isinstance(result, dict):
                raise QdrantRoutingIndexError("Qdrant scroll response has no result object")
            points = result.get("points", [])
            if not isinstance(points, list):
                raise QdrantRoutingIndexError("Qdrant scroll response has invalid points")
            records.extend(_card_from_point(point, scope) for point in points)
            next_offset = result.get("next_page_offset")
            if next_offset is None:
                return records
            if not isinstance(next_offset, (str, int)):
                raise QdrantRoutingIndexError("Qdrant scroll response has invalid page offset")
            offset = next_offset
        raise QdrantRoutingIndexError("Qdrant scroll page limit exceeded for routing projection")

    async def _semantic_search(
        self,
        query: RoutingQuery,
        visible_cards: Sequence[RetrievalCard],
        *,
        use_e5: bool,
        use_colbert: bool,
    ) -> list[RoutingSearchResult]:
        channel_models: list[tuple[RoutingEvidenceChannel, VectorRepresentation, str]] = []
        if use_e5:
            if not self._e5_model_id:
                raise QdrantRoutingIndexError("E5 routing model is not configured")
            channel_models.append((
                RoutingEvidenceChannel.QDRANT_E5,
                VectorRepresentation.DENSE_E5,
                self._e5_model_id,
            ))
        if not self._bm25_model_id:
            raise QdrantRoutingIndexError("BM25 routing model is not configured")
        channel_models.append((
            RoutingEvidenceChannel.QDRANT_BM25,
            VectorRepresentation.SPARSE_BM25,
            self._bm25_model_id,
        ))

        scopes = _visible_scopes(query.tenant_id)
        requests = [
            self._query_channel(scope, query, channel, representation, model_id)
            for scope in scopes
            for channel, representation, model_id in channel_models
        ]
        grouped_hits = await gather(*requests)
        allowed_card_keys = {card.card_key for card in visible_cards}
        hits_by_card: dict[str, dict[RoutingEvidenceChannel, _QdrantChannelHit]] = {}
        for channel_hits in grouped_hits:
            for hit in channel_hits:
                if hit.card.card_key in allowed_card_keys:
                    hits_by_card.setdefault(hit.card.card_key, {})[hit.channel] = hit
        if not hits_by_card:
            return []
        self._assign_global_channel_ranks(hits_by_card)

        if use_colbert and self._colbert_model_id and all(
            card.vector_readiness[VectorRepresentation.LATE_COLBERT]
            for card in visible_cards
        ):
            try:
                colbert_hits = await self._colbert_rerank(query, hits_by_card)
            except QdrantRoutingIndexUnavailable:
                colbert_hits = []
            for hit in colbert_hits:
                if hit.card.card_key in hits_by_card:
                    hits_by_card[hit.card.card_key][hit.channel] = hit
            self._assign_global_channel_ranks(hits_by_card)

        available_channels = {
            channel
            for channel_hits in hits_by_card.values()
            for channel in channel_hits
        }
        maximum_rrf = len(available_channels) / (self._rrf_k + 1)
        results: list[RoutingSearchResult] = []
        for card_key, channel_hits in hits_by_card.items():
            rrf_raw = sum(self._rrf(hit.rank) for hit in channel_hits.values())
            fused_score = rrf_raw / maximum_rrf if maximum_rrf else 0.0
            card = next(card for card in visible_cards if card.card_key == card_key)
            matched_terms = sorted(_tokens(query.text).intersection(_tokens(card.embedding_text())))
            positive = _matched_phrases(query.text, card.positive_examples)
            negative = _matched_phrases(query.text, card.negative_examples)
            channel_evidence = [
                RoutingChannelEvidence(
                    channel=hit.channel,
                    raw_score=round(hit.raw_score, 6),
                    contribution=round(self._rrf(hit.rank) / maximum_rrf, 6),
                    rank=hit.rank,
                    details=[f"scope={hit.scope}", f"using={_representation_for_channel(hit.channel).value}"],
                )
                for hit in sorted(channel_hits.values(), key=lambda item: item.channel.value)
            ]
            channel_evidence.append(RoutingChannelEvidence(
                channel=RoutingEvidenceChannel.RRF,
                raw_score=round(rrf_raw, 8),
                contribution=round(fused_score, 6),
                details=[f"{len(channel_hits)} rank channel(s)", f"rrf_k={self._rrf_k}"],
            ))
            if matched_terms or positive or negative:
                lexical_score = min(1.0, len(matched_terms) / max(1, len(_tokens(query.text))))
                channel_evidence.append(RoutingChannelEvidence(
                    channel=RoutingEvidenceChannel.LEXICAL_RULES,
                    raw_score=round(lexical_score, 6),
                    contribution=0.0,
                    details=[f"{len(matched_terms)} lexical term(s)", *positive, *negative],
                ))
            result = scored_routing_result(
                query=query,
                card=card,
                base_score=fused_score,
                channel_evidence=channel_evidence,
                matched_terms=matched_terms,
                matched_positive_examples=positive,
                matched_negative_examples=negative,
            )
            if result.score > 0:
                results.append(result)
        results.sort(key=lambda item: (-item.score, item.card.entity_type.value, item.card.entity_id))
        return results[:query.top_k]

    async def _query_channel(
        self,
        scope: str,
        query: RoutingQuery,
        channel: RoutingEvidenceChannel,
        representation: VectorRepresentation,
        model_id: str,
        *,
        point_ids: Sequence[str] | None = None,
    ) -> list[_QdrantChannelHit]:
        body = {
            "query": {"text": query.text, "model": model_id},
            "using": representation.value,
            "filter": _query_filter(scope, query, point_ids=point_ids),
            "limit": self._candidate_top_k if point_ids is None else len(point_ids),
            "with_payload": True,
            "with_vector": False,
        }
        payload = await self._request(
            "POST",
            f"/collections/{self._collection_name}/points/query",
            json=body,
        )
        hits: list[_QdrantChannelHit] = []
        for rank, point in enumerate(_query_result_points(payload), start=1):
            card = _card_from_point(point, scope)
            score = point.get("score") if isinstance(point, Mapping) else None
            if not isinstance(score, (int, float)):
                raise QdrantRoutingIndexError("Qdrant query point has no numeric score")
            point_id = point.get("id") if isinstance(point, Mapping) else None
            if not isinstance(point_id, (str, int)):
                raise QdrantRoutingIndexError("Qdrant query point has no supported id")
            hits.append(_QdrantChannelHit(
                card=card,
                point_id=str(point_id),
                scope=scope,
                channel=channel,
                raw_score=float(score),
                rank=rank,
            ))
        return hits

    async def _colbert_rerank(
        self,
        query: RoutingQuery,
        hits_by_card: Mapping[str, Mapping[RoutingEvidenceChannel, _QdrantChannelHit]],
    ) -> list[_QdrantChannelHit]:
        if not self._colbert_model_id:
            return []
        top_cards = sorted(
            hits_by_card.values(),
            key=lambda channel_hits: (-sum(self._rrf(hit.rank) for hit in channel_hits.values()), next(iter(channel_hits.values())).card.card_key),
        )[:self._rerank_top_k]
        point_ids_by_scope: dict[str, list[str]] = {}
        for channel_hits in top_cards:
            hit = next(iter(channel_hits.values()))
            point_ids_by_scope.setdefault(hit.scope, []).append(hit.point_id)
        requests = [
            self._query_channel(
                scope,
                query,
                RoutingEvidenceChannel.COLBERT,
                VectorRepresentation.LATE_COLBERT,
                self._colbert_model_id,
                point_ids=point_ids,
            )
            for scope, point_ids in point_ids_by_scope.items()
        ]
        results = await gather(*requests)
        return [hit for scope_hits in results for hit in scope_hits]

    def _assign_global_channel_ranks(
        self,
        hits_by_card: dict[str, dict[RoutingEvidenceChannel, _QdrantChannelHit]],
    ) -> None:
        for channel in RoutingEvidenceChannel:
            channel_hits = [hits[channel] for hits in hits_by_card.values() if channel in hits]
            for rank, hit in enumerate(sorted(channel_hits, key=lambda item: (-item.raw_score, item.card.card_key)), start=1):
                hits_by_card[hit.card.card_key][channel] = _QdrantChannelHit(
                    card=hit.card,
                    point_id=hit.point_id,
                    scope=hit.scope,
                    channel=hit.channel,
                    raw_score=hit.raw_score,
                    rank=rank,
                )

    def _rrf(self, rank: int) -> float:
        return 1.0 / (self._rrf_k + rank)

    def _semantic_query_enabled(self) -> bool:
        return bool(self._cloud_inference_enabled and self._e5_model_id and self._bm25_model_id)

    async def _fallback_or_raise(
        self,
        query: RoutingQuery,
        error: QdrantRoutingIndexUnavailable,
    ) -> list[RoutingSearchResult]:
        if self._fallback_index is not None:
            return await self._fallback_index.search(query)
        raise error

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = await self._request_response(method, path, **kwargs)
        self._raise_for_error(response)
        try:
            return response.json()
        except ValueError as exc:
            raise QdrantRoutingIndexError("Qdrant returned invalid JSON") from exc

    async def _request_response(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        client = self._client_for_request()
        try:
            response = await client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise QdrantRoutingIndexUnavailable(f"Qdrant request failed: {exc}") from exc
        if response.status_code in {408, 425, 429} or response.status_code >= 500:
            raise QdrantRoutingIndexUnavailable(
                f"Qdrant returned temporary HTTP {response.status_code}"
            )
        return response

    def _raise_for_error(self, response: httpx.Response) -> None:
        if response.is_error:
            raise QdrantRoutingIndexError(
                f"Qdrant returned HTTP {response.status_code}: {_response_detail(response)}"
            )

    def _validate_existing_schema(self, response: httpx.Response) -> None:
        try:
            payload = response.json()
            result = payload["result"]
            params = result["config"]["params"]
            vectors = params["vectors"]
            sparse_vectors = params["sparse_vectors"]
            dense_size = vectors[VectorRepresentation.DENSE_E5.value]["size"]
            colbert_size = vectors[VectorRepresentation.LATE_COLBERT.value]["size"]
        except (KeyError, TypeError, ValueError) as exc:
            raise QdrantRoutingIndexError("Qdrant collection has an unreadable routing schema") from exc
        if (
            dense_size != self._collection_schema.dense_e5_size
            or colbert_size != self._collection_schema.late_colbert_size
            or VectorRepresentation.SPARSE_BM25.value not in sparse_vectors
        ):
            raise QdrantRoutingIndexError(
                "Qdrant collection schema does not match configured named-vector sizes"
            )

    def _client_for_request(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"api-key": self._api_key} if self._api_key else {}
            self._client = httpx.AsyncClient(
                base_url=self._url,
                headers=headers,
                timeout=self._timeout_seconds,
                transport=self._transport,
            )
        return self._client


def _point_id(card: RetrievalCard) -> str:
    return str(uuid5(NAMESPACE_URL, f"academic-pipeline-engine:routing:{card.card_key}"))


def _card_key(
    entity_type: RoutingEntityType,
    entity_id: str,
    version: int,
    tenant_id: UUID | None,
) -> str:
    scope = str(tenant_id) if tenant_id is not None else "global"
    return f"{scope}:{entity_type.value}:{entity_id}:v{version}"


def _payload(card: RetrievalCard) -> dict[str, Any]:
    scope = _scope(card.tenant_id)
    return {
        "card": card.model_dump(mode="json"),
        "card_key": card.card_key,
        "scope": scope,
        "entity_type": card.entity_type.value,
        "entity_id": card.entity_id,
        "version": card.version,
        "active": card.active,
    }


def _scope(tenant_id: UUID | None) -> str:
    return "global" if tenant_id is None else f"tenant:{tenant_id}"


def _visible_scopes(tenant_id: UUID | None) -> tuple[str, ...]:
    if tenant_id is None:
        return ("global",)
    return ("global", _scope(tenant_id))


def _scope_filter(scope: str, entity_types: set[RoutingEntityType]) -> dict[str, Any]:
    must: list[dict[str, Any]] = [{"key": "scope", "match": {"value": scope}}]
    if len(entity_types) == 1:
        entity_type = next(iter(entity_types))
        must.append({"key": "entity_type", "match": {"value": entity_type.value}})
    return {"must": must}


def _query_filter(
    scope: str,
    query: RoutingQuery,
    *,
    point_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    filter_payload = _scope_filter(scope, query.entity_types)
    must = filter_payload["must"]
    if not query.include_inactive:
        must.append({"key": "active", "match": {"value": True}})
    if point_ids:
        must.append({"has_id": list(point_ids)})
    return filter_payload


def _query_result_points(payload: Any) -> list[Mapping[str, Any]]:
    if not isinstance(payload, Mapping):
        raise QdrantRoutingIndexError("Qdrant query response is not an object")
    result = payload.get("result")
    points = result.get("points") if isinstance(result, Mapping) else result
    if not isinstance(points, list) or not all(isinstance(point, Mapping) for point in points):
        raise QdrantRoutingIndexError("Qdrant query response has invalid points")
    return list(points)


def _representation_for_channel(channel: RoutingEvidenceChannel) -> VectorRepresentation:
    representations = {
        RoutingEvidenceChannel.QDRANT_E5: VectorRepresentation.DENSE_E5,
        RoutingEvidenceChannel.QDRANT_BM25: VectorRepresentation.SPARSE_BM25,
        RoutingEvidenceChannel.COLBERT: VectorRepresentation.LATE_COLBERT,
    }
    try:
        return representations[channel]
    except KeyError as exc:
        raise ValueError(f"routing channel has no Qdrant representation: {channel.value}") from exc


def _clean_model_id(value: str | None) -> str | None:
    cleaned = value.strip() if isinstance(value, str) else ""
    return cleaned or None


def _card_from_point(point: Any, expected_scope: str) -> RetrievalCard:
    if not isinstance(point, Mapping):
        raise QdrantRoutingIndexError("Qdrant point is not an object")
    payload = point.get("payload")
    if not isinstance(payload, Mapping):
        raise QdrantRoutingIndexError("Qdrant point has no routing payload")
    raw_card = payload.get("card")
    if not isinstance(raw_card, Mapping):
        raise QdrantRoutingIndexError("Qdrant point has no routing card")
    try:
        card = RetrievalCard.model_validate(raw_card)
    except ValueError as exc:
        raise QdrantRoutingIndexError("Qdrant point contains an invalid routing card") from exc
    actual_scope = _scope(card.tenant_id)
    if payload.get("scope") != actual_scope or actual_scope != expected_scope:
        raise QdrantRoutingIndexError("Qdrant point scope does not match its routing card")
    return card


def _response_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:200]
    if isinstance(payload, Mapping):
        status = payload.get("status")
        if isinstance(status, Mapping) and isinstance(status.get("error"), str):
            return status["error"]
        if isinstance(payload.get("message"), str):
            return payload["message"]
    return str(payload)[:200]
