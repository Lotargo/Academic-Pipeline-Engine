import json

import pytest

from academic_pe.core.secrets import SecretResolver
from academic_pe.instructions import InstructionRole, SkillManifest
from academic_pe.manifests import ArtifactManifestLoader, ArtifactManifestResolver
from academic_pe.routing import (
    ArtifactCandidate,
    ConfidenceBand,
    GraphEdgeType,
    ProviderInfrastructureConfig,
    RoutingDecision,
    SkillGraph,
    SkillGraphEdge,
)


def test_secret_resolver_prefers_environment_and_supports_standard_names(tmp_path, monkeypatch):
    path = tmp_path / "secrets.json"
    path.write_text(json.dumps({"JINA_API_KEY": "file-key", "custom_api_API_KEY": "unused"}), encoding="utf-8")
    monkeypatch.setenv("JINA_API_KEY", "environment-key")

    resolver = SecretResolver(path)

    assert resolver.resolve("jina") == "environment-key"
    monkeypatch.delenv("JINA_API_KEY")
    assert resolver.resolve("JINA_API_KEY") == "file-key"
    assert resolver.resolve("missing_provider") is None


def test_secret_resolver_saves_canonical_name(tmp_path):
    path = tmp_path / "config" / "secrets.json"
    resolver = SecretResolver(path)
    resolver.save("langsearch", "local-key")

    assert json.loads(path.read_text(encoding="utf-8")) == {"LANGSEARCH_API_KEY": "local-key"}
    assert resolver.resolve("LANGSEARCH_API_KEY") == "local-key"


def test_provider_config_keeps_unknown_qdrant_model_ids_unset():
    config = ProviderInfrastructureConfig.from_yaml()

    assert config.routing.collection_name == "routing_knowledge"
    assert config.providers.jina.dense_model == "jina-embeddings-v5-text-nano"
    assert config.providers.qdrant.multilingual_dense_model_id is None
    assert config.providers.qdrant.sparse_model_id is None
    assert config.providers.qdrant.late_interaction_model_id is None


def test_routing_decision_uses_margin_and_fallback_band():
    decision = RoutingDecision.from_candidates(
        [
            ArtifactCandidate(artifact_id="report", routing_score=0.85),
            ArtifactCandidate(artifact_id="academic_paper", routing_score=0.75),
        ],
        fallback_depth=1,
        active_retrieval_path="e5_bm25",
    )

    assert decision.score_margin == pytest.approx(0.10)
    assert decision.confidence_band is ConfidenceBand.PLANNER_REQUIRED
    assert decision.planner_required


def test_manifest_resolver_exposes_typed_routing_evidence(tmp_path):
    path = tmp_path / "artifact_manifests.yaml"
    path.write_text(
        """
artifacts:
  - id: report
    artifact_type: report
  - id: unknown_freeform
    artifact_type: unknown_freeform
""",
        encoding="utf-8",
    )
    resolver = ArtifactManifestResolver(manifests=ArtifactManifestLoader(path).load())

    local = resolver.resolve(topic="Quarterly report", instructions="Summarize findings")
    override = resolver.resolve(topic="Unknown", artifact_override="report")

    assert local.routing_decision.selected_artifact_id == "report"
    assert local.routing_decision.active_retrieval_path == "local_rules_only"
    assert local.routing_decision.fallback_depth == 3
    assert local.metadata()["routing_decision"]["confidence_band"] == "planner_required"
    assert override.routing_decision.confidence_band is ConfidenceBand.DIRECT
    assert override.routing_decision.top_score == 1.0


def test_skill_graph_builds_role_scoped_plan_and_gates():
    graph = SkillGraph.from_yaml()

    plan = graph.build_plan(
        ["source_triangulation"],
        artifact_id="report",
        role=InstructionRole.RESEARCHER,
        available_capabilities={"source_cards"},
        reasons={"source_triangulation": "material web claim"},
    )

    assert plan.ordered_skill_ids == ["source_triangulation"]
    assert plan.gate_ids == ["evidence_integrity"]
    assert not plan.planner_required
    assert plan.reasons["source_triangulation"] == "material web claim"


def test_skill_graph_marks_missing_capability_and_rejects_incompatible_artifact():
    graph = SkillGraph.from_yaml()

    plan = graph.build_plan(["calculation_audit"], artifact_id="report")
    assert plan.planner_required
    assert plan.unresolved_conflicts == ["calculation_audit requires calculation_ledger"]

    with pytest.raises(ValueError, match="incompatible"):
        graph.build_plan(["concise_technical"], artifact_id="creative_poem")


def test_skill_graph_orders_dependencies_and_rejects_cycles():
    first = SkillManifest(
        skill_id="first",
        description="first",
        fragments={InstructionRole.WRITER: "first"},
    )
    second = SkillManifest(
        skill_id="second",
        description="second",
        fragments={InstructionRole.WRITER: "second"},
    )
    edge = SkillGraphEdge(source="skill:second", relation=GraphEdgeType.REQUIRES, target="skill:first")
    graph = SkillGraph([first, second], [edge])
    assert graph.build_plan(["second", "first"]).ordered_skill_ids == ["first", "second"]

    reverse = SkillGraphEdge(source="skill:first", relation=GraphEdgeType.REQUIRES, target="skill:second")
    with pytest.raises(ValueError, match="cycle"):
        SkillGraph([first, second], [edge, reverse]).build_plan(["first", "second"])


def test_skill_graph_rejects_semantically_invalid_edge_shape():
    manifest = SkillManifest(
        skill_id="bounded",
        description="bounded",
        fragments={InstructionRole.WRITER: "bounded"},
    )
    invalid = SkillGraphEdge(
        source="gate:editorial_integrity",
        relation=GraphEdgeType.REQUIRES,
        target="skill:bounded",
    )
    with pytest.raises(ValueError, match="invalid requires edge"):
        SkillGraph([manifest], [invalid])
