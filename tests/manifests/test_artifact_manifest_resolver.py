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
    assert resolved.contract.clauses == ["academic_mode"]
    assert "research_paper_structure" in resolved.contract.forbid
    assert "(artifact creative_poem)" in resolved.contract_sexpr
    assert "(clauses academic_mode)" in resolved.contract_sexpr
    assert resolved.metadata()["decision_summary"] == {
        "selected_manifest": "creative_poem",
        "manifest_version": 1,
        "artifact": "creative_poem",
        "confidence": 0.7,
        "matched_phrases": ["poem"],
        "mode": "academic",
        "summary": "Matched artifact cues: poem. Preserving creative poem behavior in academic mode.",
        "ambiguity_notes": [],
    }


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


def test_resolver_accepts_explicit_execution_mode(tmp_path):
    resolved = _resolver(tmp_path).resolve(
        topic="Project README",
        instructions="Add installation and usage sections.",
        execution_mode="academic",
    )

    assert resolved.contract.execution_mode == "academic"
    assert resolved.contract.clauses == ["academic_mode"]
    assert resolved.contract.requirements["rigor"] == "reproducibility"


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
    assert resolved.contract.clauses == ["academic_mode"]
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
    assert resolved.metadata()["decision_summary"]["summary"].startswith(
        "Inherited artifact behavior from continuation metadata."
    )


def test_resolver_infers_manifest_from_legacy_continuation_metadata(tmp_path):
    resolved = _resolver(tmp_path).resolve(
        topic="Continue",
        instructions="Add one more part in the same style.",
        continuation_metadata={
            "previous_prompt": "Topic: Lady in Red\nInstructions: Write a poem with 12 lines.",
            "document_plan": "A short stanza-based poetic plan.",
        },
    )

    assert resolved.manifest.id == "creative_poem"
    assert "poem" in resolved.evidence.matched_phrases
    assert resolved.evidence.confidence <= 0.75
    assert "legacy continuation metadata" in resolved.evidence.ambiguity_notes[0]
    assert resolved.metadata()["decision_summary"]["summary"].startswith(
        "Inferred artifact behavior from legacy continuation metadata."
    )


def test_resolver_current_artifact_cue_overrides_previous_manifest(tmp_path):
    resolved = _resolver(tmp_path).resolve(
        topic="Project README",
        instructions="Convert this into installation and usage documentation.",
        continuation_metadata={
            "resolved_manifest": {
                "id": "creative_poem",
                "version": 1,
            }
        },
    )

    assert resolved.manifest.id == "technical_readme"
    assert "readme" in resolved.evidence.matched_phrases


def test_resolver_respects_user_artifact_override(tmp_path):
    resolved = _resolver(tmp_path).resolve(
        topic="Project README",
        instructions="Add installation and usage sections.",
        artifact_override="creative_poem",
    )
    assert resolved.manifest.id == "creative_poem"
    assert resolved.evidence.confidence == 1.0
    assert resolved.evidence.matched_phrases == ["user override"]


def test_resolver_enforces_style_preservation_on_low_confidence_continuation(tmp_path):
    resolved = _resolver(tmp_path).resolve(
        topic="A strange niche artifact",
        instructions="Make it exactly in this odd structure.",
        mode="continuation",
    )
    assert resolved.manifest.id == "unknown_freeform"
    assert resolved.evidence.confidence == 0.25
    assert resolved.contract.requirements.get("preserve_style_and_avoid_new_structure") is True
