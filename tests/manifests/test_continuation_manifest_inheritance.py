import pytest
from academic_pe.manifests import ArtifactManifestResolver, ArtifactManifestLoader
from tests.manifests.test_artifact_manifest_resolver import _manifest_path


def _resolver(tmp_path):
    manifests = ArtifactManifestLoader(_manifest_path(tmp_path)).load()
    return ArtifactManifestResolver(manifests=manifests)


def test_resolver_inherits_manifest_id_and_version(tmp_path):
    # Enforces Priority 2: resolved_manifest inherits from continuation metadata
    resolved = _resolver(tmp_path).resolve(
        topic="Continue",
        instructions="Make another entry",
        continuation_metadata={
            "resolved_manifest": {
                "id": "technical_readme",
                "version": 1
            }
        }
    )

    assert resolved.manifest.id == "technical_readme"
    assert resolved.evidence.confidence == 0.9
    assert resolved.evidence.matched_phrases == ["previous resolved manifest"]


def test_resolver_infers_from_previous_user_prompt(tmp_path):
    # Enforces Priority 3: resolver infers manifest from previous_prompt when resolved_manifest is missing
    resolved = _resolver(tmp_path).resolve(
        topic="Continue",
        instructions="Add a section",
        continuation_metadata={
            "previous_prompt": "Create a README for a python package."
        }
    )

    assert resolved.manifest.id == "technical_readme"
    # Priority 3 confidence is capped at 0.75
    assert resolved.evidence.confidence <= 0.75
    assert "previous user prompt" in resolved.evidence.ambiguity_notes[0]


def test_resolver_infers_from_document_plan(tmp_path):
    # Enforces Priority 4: resolver infers from document_plan
    resolved = _resolver(tmp_path).resolve(
        topic="Continue",
        instructions="Add a section",
        continuation_metadata={
            "document_plan": "Stanza-oriented verses."
        }
    )

    assert resolved.manifest.id == "creative_poem"
    # Priority 4 confidence is capped at 0.70
    assert resolved.evidence.confidence <= 0.70
    assert "previous document plan" in resolved.evidence.ambiguity_notes[0]


def test_resolver_infers_from_context_text(tmp_path):
    # Enforces Priority 5: resolver infers from context document text/style
    resolved = _resolver(tmp_path).resolve(
        topic="Continue",
        instructions="Add a section",
        continuation_metadata={
            "context": {
                "readme_file": "Overview\nInstallation\nUsage"
            }
        }
    )

    assert resolved.manifest.id == "technical_readme"
    # Priority 5 confidence is capped at 0.65
    assert resolved.evidence.confidence == 0.65
    assert "previous document text and structure" in resolved.evidence.ambiguity_notes[0]


def test_resolver_style_preservation_on_low_confidence_fallback(tmp_path):
    # Low confidence fallback: resolver applies style preservation and avoids new structure
    resolved = _resolver(tmp_path).resolve(
        topic="Some custom niche document",
        instructions="Do something very specific and unique",
        mode="continuation",
        continuation_metadata={
            "context": {
                "text": "Some text in a unique structure."
            }
        }
    )

    # Resolves to unknown_freeform
    assert resolved.manifest.id == "unknown_freeform"
    assert resolved.evidence.confidence <= 0.65
    assert resolved.contract.requirements.get("preserve_style_and_avoid_new_structure") is True
    assert resolved.contract.requirements.get("preserve_source_voice") is True
    assert resolved.contract.requirements.get("avoid_new_sections_unless_requested") is True
    assert resolved.contract.requirements.get("source_section_order") == ["text"]
    assert resolved.contract.requirements.get("source_style_sample") == "Some text in a unique structure."
    assert '(requirement source_section_order ("text"))' in resolved.contract_sexpr
    assert '(requirement source_style_sample "Some text in a unique structure.")' in resolved.contract_sexpr


def test_resolver_user_override_wins_over_continuation(tmp_path):
    # User override (Priority 0) wins over resolved_manifest from continuation
    resolved = _resolver(tmp_path).resolve(
        topic="Continue readme",
        instructions="Write the readme",
        artifact_override="creative_poem",
        continuation_metadata={
            "resolved_manifest": {
                "id": "technical_readme",
                "version": 1
            }
        }
    )

    assert resolved.manifest.id == "creative_poem"
    assert resolved.evidence.confidence == 1.0
    assert resolved.evidence.matched_phrases == ["user override"]
