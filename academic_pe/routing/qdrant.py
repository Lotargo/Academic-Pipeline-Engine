from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

import httpx

from academic_pe.core.secrets import SecretResolver
from academic_pe.routing.cards import RetrievalCard, RoutingEntityType, VectorRepresentation
from academic_pe.routing.config import ProviderInfrastructureConfig
from academic_pe.routing.index import (
    InMemoryRoutingIndex,
    RoutingIndexHealth,
    RoutingQuery,
    RoutingSearchResult,
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


class QdrantRoutingIndex:
    """Optional Qdrant projection with the same safe visibility rules as local search.

    A card-only projection remains searchable through the deterministic local
    scoring layer.  Semantic Qdrant queries are intentionally not enabled until
    exact model IDs and validated embeddings are available; this keeps local
    generation independent of Qdrant inference.
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

        self._url = normalized_url
        self._collection_name = collection_name
        self._api_key = api_key.strip() if api_key and api_key.strip() else None
        self._timeout_seconds = timeout_seconds
        self._max_scroll_pages = max_scroll_pages
        self._collection_schema = collection_schema or QdrantCollectionSchema()
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
        cards: list[RetrievalCard] = []
        for scope in _visible_scopes(query.tenant_id):
            cards.extend(await self._scroll_scope(scope, query))

        # This mirrors the local adapter's latest-version, inactive-tombstone,
        # tenant-override and penalty semantics until vector queries are enabled.
        local_projection = InMemoryRoutingIndex()
        await local_projection.upsert(cards)
        return await local_projection.search(query)

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
