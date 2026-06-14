from academic_pe.manifests.loader import ArtifactManifestLoader, ManifestLoadError
from academic_pe.manifests.models import ArtifactManifest, ArtifactModeOverlay
from academic_pe.manifests.evidence import ManifestSelectionEvidence
from academic_pe.manifests.fallback import ManifestFallbackError, fallback_evidence, select_fallback_manifest

__all__ = [
    "ArtifactManifest",
    "ArtifactManifestLoader",
    "ArtifactModeOverlay",
    "ArtifactManifestResolver",
    "ManifestSelectionEvidence",
    "ManifestFallbackError",
    "ManifestLoadError",
    "ResolvedArtifactManifest",
    "fallback_evidence",
    "select_fallback_manifest",
]


def __getattr__(name: str):
    if name in {"ArtifactManifestResolver", "ResolvedArtifactManifest"}:
        from academic_pe.manifests.resolver import ArtifactManifestResolver, ResolvedArtifactManifest

        values = {
            "ArtifactManifestResolver": ArtifactManifestResolver,
            "ResolvedArtifactManifest": ResolvedArtifactManifest,
        }
        return values[name]
    raise AttributeError(name)
