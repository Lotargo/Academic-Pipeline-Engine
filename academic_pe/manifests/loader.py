from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable

import yaml

from academic_pe.manifests.models import ArtifactManifest


class ManifestLoadError(ValueError):
    pass


class ArtifactManifestLoader:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> Dict[str, ArtifactManifest]:
        if not self.path.exists():
            raise ManifestLoadError(f"Artifact manifest file does not exist: {self.path}")

        with self.path.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}

        items = raw.get("artifacts") if isinstance(raw, dict) else None
        if not isinstance(items, list):
            raise ManifestLoadError("Artifact manifest file must contain an 'artifacts' list.")

        return self._parse_items(items)

    def _parse_items(self, items: Iterable[object]) -> Dict[str, ArtifactManifest]:
        manifests: Dict[str, ArtifactManifest] = {}
        for item in items:
            if not isinstance(item, dict):
                raise ManifestLoadError("Each artifact manifest entry must be a mapping.")
            manifest = ArtifactManifest(**item)
            if manifest.id in manifests:
                raise ManifestLoadError(f"Duplicate artifact manifest id: {manifest.id}")
            manifests[manifest.id] = manifest
        return manifests
