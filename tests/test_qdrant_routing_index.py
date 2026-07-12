import asyncio
import json
from uuid import uuid4

import httpx
import pytest

from academic_pe.routing import (
    ProviderInfrastructureConfig,
    QdrantCollectionSchema,
    QdrantRoutingIndex,
    QdrantRoutingIndexError,
    QdrantRoutingIndexUnavailable,
    QdrantRoutingRecord,
    RetrievalCard,
    RoutingEntityType,
    RoutingFallbackPolicy,
    RoutingProviderReadiness,
    RoutingQuery,
    RoutingRetrievalPath,
    VectorRepresentation,
)
from academic_pe.core.secrets import SecretResolver


def _run(awaitable):
    return asyncio.run(awaitable)


def _card(*, entity_id="evidence", version=1, tenant_id=None, active=True, readiness=None):
    return RetrievalCard(
        entity_type=RoutingEntityType.SKILL,
        entity_id=entity_id,
        version=version,
        title="Evidence comparison",
        descriptions={"en": ["Compare independent evidence for a report claim."]},
        positive_examples=["compare evidence"],
        negative_examples=["fictional story"],
        capabilities=["evidence_synthesis"],
        compatible_artifacts=["report"],
        agent_scope=["researcher"],
        tenant_id=tenant_id,
        active=active,
        vector_readiness=readiness or {representation: False for representation in VectorRepresentation},
    )


def _index(handler):
    return QdrantRoutingIndex(
        url="https://qdrant.example.test",
        collection_name="routing_knowledge",
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )


def test_qdrant_upsert_uses_deterministic_id_and_payload_only_projection():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"status": "ok", "result": {}})

    card = _card()
    index = _index(handler)
    _run(index.upsert([card]))
    _run(index.upsert([card]))
    _run(index.aclose())

    first, second = (json.loads(request.content)["points"][0] for request in requests)
    assert first["id"] == second["id"]
    assert "vector" not in first
    assert first["payload"]["scope"] == "global"
    assert first["payload"]["card"]["negative_examples"] == ["fictional story"]
    assert requests[0].headers["api-key"] == "test-key"


def test_qdrant_vector_record_requires_matching_named_vector_readiness():
    card = _card()
    record = QdrantRoutingRecord(card=card, vectors={VectorRepresentation.DENSE_E5: [0.1, 0.2]})

    with pytest.raises(ValueError, match="vector_readiness"):
        record.to_point()

    ready = card.model_copy(update={
        "vector_readiness": {
            VectorRepresentation.DENSE_JINA: False,
            VectorRepresentation.DENSE_E5: True,
            VectorRepresentation.SPARSE_BM25: False,
            VectorRepresentation.LATE_COLBERT: False,
        }
    })
    point = QdrantRoutingRecord(
        card=ready,
        vectors={VectorRepresentation.DENSE_E5: [0.1, 0.2]},
    ).to_point()
    assert point["vector"] == {"dense_e5": [0.1, 0.2]}


def test_qdrant_search_never_requests_another_tenant_scope_and_keeps_override_rules():
    tenant_a = uuid4()
    tenant_b = uuid4()
    global_card = _card(version=3)
    tenant_card = _card(version=1, tenant_id=tenant_a)
    other_tenant_card = _card(version=9, tenant_id=tenant_b)
    seen_scopes = []

    def handler(request):
        body = json.loads(request.content)
        scope = body["filter"]["must"][0]["match"]["value"]
        seen_scopes.append(scope)
        cards = {
            "global": [global_card],
            f"tenant:{tenant_a}": [tenant_card],
            f"tenant:{tenant_b}": [other_tenant_card],
        }[scope]
        points = [
            {"id": card.card_key, "payload": {
                "card": card.model_dump(mode="json"),
                "scope": scope,
            }}
            for card in cards
        ]
        return httpx.Response(200, json={"status": "ok", "result": {"points": points}})

    index = _index(handler)
    results = _run(index.search(RoutingQuery(text="compare evidence", tenant_id=tenant_a)))
    _run(index.aclose())

    assert seen_scopes == ["global", f"tenant:{tenant_a}"]
    assert [(item.card.version, item.card.tenant_id) for item in results] == [(1, tenant_a)]


def test_qdrant_health_reports_safe_failure_without_raising():
    def handler(_request):
        return httpx.Response(503, json={"status": {"error": "maintenance"}})

    health = _run(_index(handler).healthcheck())

    assert not health.healthy
    assert health.adapter == "qdrant"
    assert "temporary HTTP 503" in health.details[0]


def test_qdrant_provisions_named_vectors_and_payload_indexes_when_missing():
    requests = []

    def handler(request):
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(404, json={"status": {"error": "missing"}})
        return httpx.Response(200, json={"status": "ok", "result": {}})

    index = QdrantRoutingIndex(
        url="https://qdrant.example.test",
        collection_name="routing_knowledge",
        collection_schema=QdrantCollectionSchema(dense_e5_size=384, late_colbert_size=128),
        transport=httpx.MockTransport(handler),
    )
    assert _run(index.ensure_collection())
    _run(index.aclose())

    create_request = requests[1]
    assert create_request.method == "PUT"
    assert create_request.url.path == "/collections/routing_knowledge"
    create_body = json.loads(create_request.content)
    assert create_body["vectors"]["dense_e5"] == {"size": 384, "distance": "Cosine"}
    assert create_body["vectors"]["late_colbert"]["multivector_config"] == {"comparator": "max_sim"}
    assert create_body["vectors"]["late_colbert"]["hnsw_config"] == {"m": 0}
    assert create_body["sparse_vectors"] == {"sparse_bm25": {}}
    index_requests = requests[2:]
    assert [json.loads(request.content)["field_name"] for request in index_requests] == [
        "scope", "entity_type", "entity_id", "active",
    ]


def test_qdrant_factory_reads_provider_config_and_standard_secret_name(tmp_path):
    secret_path = tmp_path / "secrets.json"
    secret_path.write_text('{"QDRANT_API_KEY": "test-key"}', encoding="utf-8")
    configuration = ProviderInfrastructureConfig.model_validate({
        "schema_version": 1,
        "routing": {
            "collection_name": "routing_knowledge",
            "candidate_top_k": 20,
            "rerank_top_k": 8,
            "timeout_seconds": 15,
            "max_retries": 2,
        },
        "providers": {
            "jina": {
                "dense_model": "jina-embeddings-v5-text-nano",
                "web_reranker_model": "jina-reranker-v3",
            },
            "qdrant": {
                "url": "https://qdrant.example.test",
                "cloud_inference_enabled": True,
                "sparse_model_id": "qdrant/bm25",
            },
            "langsearch": {},
        },
    })

    def handler(request):
        assert request.url.path == "/collections/routing_knowledge"
        assert request.headers["api-key"] == "test-key"
        return httpx.Response(200, json={"status": "ok", "result": {"points_count": 0}})

    index = QdrantRoutingIndex.from_provider_config(
        configuration,
        secret_resolver=SecretResolver(secret_path),
        transport=httpx.MockTransport(handler),
    )
    health = _run(index.healthcheck())
    _run(index.aclose())

    assert health.healthy


def test_qdrant_distinguishes_unavailable_and_configuration_errors():
    def unavailable(_request):
        raise httpx.ConnectError("offline")

    with pytest.raises(QdrantRoutingIndexUnavailable):
        _run(_index(unavailable).search(RoutingQuery(text="compare evidence")))

    def invalid(_request):
        return httpx.Response(401, json={"message": "invalid api key"})

    with pytest.raises(QdrantRoutingIndexError, match="HTTP 401"):
        _run(_index(invalid).search(RoutingQuery(text="compare evidence")))


def test_fallback_policy_requires_all_active_cards_for_each_vector_channel():
    cards = [
        _card(readiness={
            VectorRepresentation.DENSE_JINA: True,
            VectorRepresentation.DENSE_E5: True,
            VectorRepresentation.SPARSE_BM25: True,
            VectorRepresentation.LATE_COLBERT: False,
        }),
        _card(entity_id="secondary", readiness={
            VectorRepresentation.DENSE_JINA: False,
            VectorRepresentation.DENSE_E5: True,
            VectorRepresentation.SPARSE_BM25: True,
            VectorRepresentation.LATE_COLBERT: False,
        }),
    ]
    readiness = RoutingProviderReadiness.from_cards(
        cards,
        qdrant_healthy=True,
        jina_healthy=True,
    )

    choice = RoutingFallbackPolicy().select(readiness)

    assert choice.active_retrieval_path is RoutingRetrievalPath.E5_BM25
    assert choice.fallback_depth == 1


def test_fallback_policy_escalates_to_local_rules_when_qdrant_is_down():
    choice = RoutingFallbackPolicy().select(RoutingProviderReadiness())

    assert choice.active_retrieval_path is RoutingRetrievalPath.LOCAL_RULES_ONLY
    assert choice.fallback_depth == 3
    assert choice.planner_required


def test_readiness_ignores_superseded_card_versions_and_inactive_tombstones():
    ready = {
        VectorRepresentation.DENSE_JINA: True,
        VectorRepresentation.DENSE_E5: True,
        VectorRepresentation.SPARSE_BM25: True,
        VectorRepresentation.LATE_COLBERT: False,
    }
    readiness = RoutingProviderReadiness.from_cards(
        [
            _card(version=1),
            _card(version=2, readiness=ready),
            _card(entity_id="removed", version=1, readiness=ready),
            _card(entity_id="removed", version=2, active=False),
        ],
        qdrant_healthy=True,
        jina_healthy=True,
    )

    choice = RoutingFallbackPolicy().select(readiness)

    assert choice.active_retrieval_path is RoutingRetrievalPath.JINA_BM25
