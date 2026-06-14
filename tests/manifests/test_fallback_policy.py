import pytest

from academic_pe.manifests import ManifestFallbackError, fallback_evidence, select_fallback_manifest
from academic_pe.manifests.models import ArtifactManifest


def test_fallback_policy_prefers_unknown_freeform_manifest():
    manifests = {
        "creative_poem": ArtifactManifest(id="creative_poem", artifact_type="creative_poem"),
        "unknown_freeform": ArtifactManifest(id="unknown_freeform", artifact_type="unknown_freeform"),
    }

    fallback = select_fallback_manifest(manifests)
    evidence = fallback_evidence(fallback)

    assert fallback.id == "unknown_freeform"
    assert evidence.manifest_id == "unknown_freeform"
    assert evidence.confidence == 0.25
    assert "preserve-first fallback" in evidence.ambiguity_notes[0]


def test_fallback_policy_uses_first_manifest_when_unknown_is_missing():
    manifests = {
        "creative_poem": ArtifactManifest(id="creative_poem", artifact_type="creative_poem"),
    }

    assert select_fallback_manifest(manifests).id == "creative_poem"


def test_fallback_policy_rejects_empty_manifest_collection():
    with pytest.raises(ManifestFallbackError, match="No artifact manifests are available"):
        select_fallback_manifest({})
