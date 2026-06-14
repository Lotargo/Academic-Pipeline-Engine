from __future__ import annotations

from typing import Dict

from academic_pe.manifests.evidence import ManifestSelectionEvidence
from academic_pe.manifests.models import ArtifactManifest


class ManifestFallbackError(ValueError):
    pass


def select_fallback_manifest(manifests: Dict[str, ArtifactManifest]) -> ArtifactManifest:
    if "unknown_freeform" in manifests:
        return manifests["unknown_freeform"]
    if manifests:
        return next(iter(manifests.values()))
    raise ManifestFallbackError("No artifact manifests are available.")


def fallback_evidence(manifest: ArtifactManifest) -> ManifestSelectionEvidence:
    return ManifestSelectionEvidence(
        manifest_id=manifest.id,
        confidence=0.25,
        matched_phrases=[],
        ambiguity_notes=["No strong artifact cues matched; using preserve-first fallback."],
    )
