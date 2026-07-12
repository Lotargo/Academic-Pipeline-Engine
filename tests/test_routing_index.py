import asyncio
from uuid import uuid4

from academic_pe.instructions import SkillRegistry
from academic_pe.manifests import ArtifactManifestLoader
from academic_pe.routing import (
    InMemoryRoutingIndex,
    RetrievalCard,
    RoutingEntityType,
    RoutingIndex,
    RoutingQuery,
    VectorRepresentation,
    artifact_retrieval_cards,
    skill_retrieval_cards,
)


def _run(awaitable):
    return asyncio.run(awaitable)


def _card(
    entity_id: str,
    *,
    version: int = 1,
    tenant_id=None,
    active: bool = True,
    negative_examples=(),
):
    return RetrievalCard(
        entity_type=RoutingEntityType.SKILL,
        entity_id=entity_id,
        version=version,
        title="Evidence comparison",
        descriptions={"en": ["Compare evidence for a material report claim."]},
        positive_examples=["compare evidence"],
        negative_examples=list(negative_examples),
        capabilities=["evidence_synthesis"],
        compatible_artifacts=["report"],
        agent_scope=["researcher"],
        tenant_id=tenant_id,
        active=active,
    )


def test_canonical_manifests_build_bilingual_cards_without_negative_embedding_text():
    artifacts = ArtifactManifestLoader("config/artifact_manifests.yaml").load()
    artifact_cards = artifact_retrieval_cards(artifacts.values())
    skill_cards = skill_retrieval_cards(SkillRegistry.from_yaml().manifests)

    report = next(card for card in artifact_cards if card.entity_id == "report")
    source_skill = next(card for card in skill_cards if card.entity_id == "source_triangulation")

    assert set(report.descriptions) == {"en", "ru"}
    assert "fairy tale" in report.negative_text()
    assert "fairy tale" not in report.embedding_text()
    assert source_skill.compatible_artifacts == ["academic_paper", "report", "plan_document", "technical_readme"]
    assert source_skill.dependencies == ["source_cards"]
    assert source_skill.vector_readiness == {
        representation: False for representation in VectorRepresentation
    }


def test_in_memory_index_ranks_artifact_and_skill_cards_with_filters():
    artifacts = ArtifactManifestLoader("config/artifact_manifests.yaml").load()
    cards = [
        *artifact_retrieval_cards(artifacts.values()),
        *skill_retrieval_cards(SkillRegistry.from_yaml().manifests),
    ]
    index = InMemoryRoutingIndex()
    _run(index.upsert(cards))

    artifact_results = _run(index.search(RoutingQuery(
        text="analytical report with findings and supporting data",
        entity_types={RoutingEntityType.ARTIFACT},
        top_k=3,
    )))
    skill_results = _run(index.search(RoutingQuery(
        text="compare independent sources for material claims",
        entity_types={RoutingEntityType.SKILL},
        artifact_id="report",
        agent_role="researcher",
    )))

    assert artifact_results[0].card.entity_id == "report"
    assert skill_results[0].card.entity_id == "source_triangulation"
    assert all(result.card.entity_type is RoutingEntityType.SKILL for result in skill_results)
    assert all("report" in result.card.compatible_artifacts for result in skill_results)


def test_negative_examples_are_a_separate_penalty_layer():
    clean = _card("clean")
    penalized = _card("penalized", negative_examples=["fictional story"])
    index = InMemoryRoutingIndex()
    _run(index.upsert([clean, penalized]))

    results = _run(index.search(RoutingQuery(
        text="compare evidence for a fictional story",
        entity_types={RoutingEntityType.SKILL},
    )))

    by_id = {result.card.entity_id: result for result in results}
    assert by_id["clean"].score > by_id["penalized"].score
    assert by_id["penalized"].matched_negative_examples == ["fictional story"]


def test_index_uses_latest_version_without_resurrecting_inactive_records():
    index = InMemoryRoutingIndex()
    _run(index.upsert([_card("versioned", version=1), _card("versioned", version=2, active=False)]))

    assert _run(index.search(RoutingQuery(text="compare evidence"))) == []
    inactive = _run(index.search(RoutingQuery(text="compare evidence", include_inactive=True)))
    assert [result.card.version for result in inactive] == [2]

    _run(index.delete("versioned", 2, entity_type=RoutingEntityType.SKILL))
    restored = _run(index.search(RoutingQuery(text="compare evidence")))
    assert [result.card.version for result in restored] == [1]


def test_tenant_card_overrides_global_card_without_cross_tenant_visibility():
    tenant_a = uuid4()
    tenant_b = uuid4()
    index = InMemoryRoutingIndex()
    _run(index.upsert([
        _card("scoped", version=3),
        _card("scoped", version=1, tenant_id=tenant_a),
        _card("scoped", version=2, tenant_id=tenant_b),
    ]))

    global_result = _run(index.search(RoutingQuery(text="compare evidence")))
    tenant_result = _run(index.search(RoutingQuery(text="compare evidence", tenant_id=tenant_a)))

    assert [(item.card.version, item.card.tenant_id) for item in global_result] == [(3, None)]
    assert [(item.card.version, item.card.tenant_id) for item in tenant_result] == [(1, tenant_a)]

    _run(index.delete("scoped", 3, entity_type=RoutingEntityType.SKILL))
    tenant_after_global_delete = _run(index.search(RoutingQuery(
        text="compare evidence",
        tenant_id=tenant_a,
    )))
    assert [(item.card.version, item.card.tenant_id) for item in tenant_after_global_delete] == [(1, tenant_a)]


def test_index_protocol_and_healthcheck_are_adapter_neutral():
    index = InMemoryRoutingIndex()
    assert isinstance(index, RoutingIndex)

    _run(index.upsert([_card("health")]))
    health = _run(index.healthcheck())

    assert health.healthy
    assert health.adapter == "in_memory"
    assert health.record_count == 1
