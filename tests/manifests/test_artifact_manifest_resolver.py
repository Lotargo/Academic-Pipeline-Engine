from academic_pe.manifests import ArtifactManifestLoader, ArtifactManifestResolver


def _manifest_path(tmp_path):
    path = tmp_path / "config" / "artifact_manifests.yaml"
    path.parent.mkdir()
    path.write_text(
        """
artifacts:
  - id: creative_poem
    version: 1
    artifact_type: creative_poem
    style: [lyrical, human]
    forbid: [academic_drift, forced_visualization]
    modes:
      academic:
        add_forbid: [research_paper_structure]
        visualization_policy: forbidden

  - id: technical_readme
    version: 1
    artifact_type: technical_readme
    style: [practical, concrete]
    forbid: [academic_drift, citations, forced_visualization]
    modes:
      academic:
        add_requirements:
          rigor: reproducibility
        visualization_policy: compatible_only

  - id: academic_paper
    version: 1
    artifact_type: academic_paper
    style: [formal, analytical]
    forbid: [unsupported_claims]
    modes:
      academic:
        add_requirements:
          evidence_discipline: true
        visualization_policy: required

  - id: unknown_freeform
    version: 1
    artifact_type: unknown_freeform
    style: [preserve_user_intent]
    forbid: [academic_drift, invented_structure, forced_visualization]
    modes:
      academic:
        add_forbid: [research_paper_structure]
        visualization_policy: compatible_only
""",
        encoding="utf-8",
    )
    return path


def _resolver(tmp_path):
    manifests = ArtifactManifestLoader(_manifest_path(tmp_path)).load()
    return ArtifactManifestResolver(manifests=manifests)


def test_resolver_selects_poem_without_forced_visualization(tmp_path):
    resolved = _resolver(tmp_path).resolve(
        topic="Lady in Red",
        instructions="Write a poem with 12 lines.",
        academic_mode=True,
        language="en",
    )

    assert resolved.manifest.id == "creative_poem"
    assert resolved.evidence.confidence > 0.5
    assert "poem" in resolved.evidence.matched_phrases
    assert resolved.contract.visualization_required is False
    assert "research_paper_structure" in resolved.contract.forbid
    assert "(artifact creative_poem)" in resolved.contract_sexpr


def test_resolver_selects_poem_from_russian_cues(tmp_path):
    resolved = _resolver(tmp_path).resolve(
        topic="Дама в красном",
        instructions="Сочинить стихотворение не менее 12 строк.",
        language="ru",
    )

    assert resolved.manifest.id == "creative_poem"
    assert any(match in {"стих", "стихотвор"} for match in resolved.evidence.matched_phrases)


def test_resolver_selects_readme_and_preserves_technical_artifact(tmp_path):
    resolved = _resolver(tmp_path).resolve(
        topic="Project README",
        instructions="Add installation, usage, and configuration sections.",
        academic_mode=True,
    )

    assert resolved.manifest.id == "technical_readme"
    assert resolved.contract.visualization_required is False
    assert resolved.contract.requirements["rigor"] == "reproducibility"
    assert "citations" in resolved.contract.forbid


def test_resolver_uses_unknown_freeform_fallback(tmp_path):
    resolved = _resolver(tmp_path).resolve(
        topic="A strange niche artifact",
        instructions="Make it exactly in this odd structure.",
    )

    assert resolved.manifest.id == "unknown_freeform"
    assert resolved.evidence.confidence == 0.25
    assert "preserve-first fallback" in resolved.evidence.ambiguity_notes[0]
    assert resolved.contract.visualization_required is False


def test_resolver_allows_visualization_for_academic_paper_academic_mode(tmp_path):
    resolved = _resolver(tmp_path).resolve(
        topic="Research paper on measurements",
        instructions="Use methodology and evidence.",
        academic_mode=True,
    )

    assert resolved.manifest.id == "academic_paper"
    assert resolved.contract.visualization_required is True
    assert resolved.contract.requirements["evidence_discipline"] is True


def test_resolver_inherits_previous_manifest_from_continuation_metadata(tmp_path):
    resolved = _resolver(tmp_path).resolve(
        topic="Add one more section",
        instructions="Continue in the same style.",
        academic_mode=False,
        continuation_metadata={
            "resolved_manifest": {
                "id": "creative_poem",
                "version": 1,
            }
        },
    )

    assert resolved.manifest.id == "creative_poem"
    assert resolved.evidence.matched_phrases == ["previous resolved manifest"]
    assert resolved.evidence.confidence == 0.9
