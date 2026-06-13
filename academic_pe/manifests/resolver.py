from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Optional

from academic_pe.contracts.compiler import compile_artifact_contract
from academic_pe.contracts.models import ArtifactContract
from academic_pe.contracts.sexpr import render_contract_sexpr
from academic_pe.manifests.evidence import ManifestSelectionEvidence
from academic_pe.manifests.loader import ArtifactManifestLoader
from academic_pe.manifests.models import ArtifactManifest


DEFAULT_ARTIFACT_MANIFEST_PATH = Path("config/artifact_manifests.yaml")


class ResolvedArtifactManifest:
    def __init__(
        self,
        manifest: ArtifactManifest,
        contract: ArtifactContract,
        evidence: ManifestSelectionEvidence,
        contract_sexpr: str,
    ):
        self.manifest = manifest
        self.contract = contract
        self.evidence = evidence
        self.contract_sexpr = contract_sexpr

    def metadata(self) -> dict:
        return {
            "resolved_manifest": self.manifest.model_dump(mode="json"),
            "resolved_contract": self.contract.model_dump(mode="json"),
            "contract_sexpr": self.contract_sexpr,
            "manifest_selection": self.evidence.model_dump(mode="json"),
        }


class ArtifactManifestResolver:
    def __init__(
        self,
        manifests: Optional[Dict[str, ArtifactManifest]] = None,
        manifest_path: str | Path = DEFAULT_ARTIFACT_MANIFEST_PATH,
    ):
        self._manifests = manifests
        self._manifest_path = Path(manifest_path)

    def resolve(
        self,
        *,
        topic: str = "",
        instructions: str = "",
        academic_mode: bool = False,
        language: str = "auto",
        mode: str = "new",
        continuation_metadata: Optional[dict] = None,
    ) -> ResolvedArtifactManifest:
        manifests = self._load_manifests()

        previous_manifest_id = self._previous_manifest_id(continuation_metadata)
        if previous_manifest_id and previous_manifest_id in manifests:
            manifest = manifests[previous_manifest_id]
            evidence = ManifestSelectionEvidence(
                manifest_id=manifest.id,
                confidence=0.9,
                matched_phrases=["previous resolved manifest"],
                ambiguity_notes=["Inherited artifact behavior from continuation metadata."],
            )
        else:
            manifest, evidence = self._select_manifest(manifests, topic, instructions)

        execution_mode = "academic" if academic_mode else "standard"
        contract = compile_artifact_contract(
            manifest,
            language=language,
            mode=mode,
            execution_mode=execution_mode,
        )
        return ResolvedArtifactManifest(
            manifest=manifest,
            contract=contract,
            evidence=evidence,
            contract_sexpr=render_contract_sexpr(contract),
        )

    def _load_manifests(self) -> Dict[str, ArtifactManifest]:
        if self._manifests is not None:
            return self._manifests
        self._manifests = ArtifactManifestLoader(self._manifest_path).load()
        return self._manifests

    def _select_manifest(
        self,
        manifests: Dict[str, ArtifactManifest],
        topic: str,
        instructions: str,
    ) -> tuple[ArtifactManifest, ManifestSelectionEvidence]:
        text = f"{topic}\n{instructions}".casefold()
        candidates = [
            ("technical_readme", ["readme", "installation", "install", "usage", "configuration", "api docs"]),
            ("creative_poem", ["poem", "poetry", "stanza", "verse", "стих", "стихотвор"]),
            ("creative_story", ["story", "fairy tale", "fiction", "narrative", "сказк", "рассказ"]),
            ("school_essay", ["school essay", "composition", "сочинение", "school-level", "for grade"]),
            ("academic_paper", ["academic paper", "research paper", "scientific paper", "methodology", "citation"]),
            ("plan_document", ["plan", "roadmap", "sprint", "milestone", "tasks", "план"]),
            ("report", ["report", "findings", "отчет", "отчёт"]),
        ]

        scored: list[tuple[str, list[str]]] = []
        for manifest_id, phrases in candidates:
            if manifest_id not in manifests:
                continue
            matches = [phrase for phrase in phrases if phrase in text]
            if matches:
                scored.append((manifest_id, matches))

        if scored:
            manifest_id, matches = max(scored, key=lambda item: len(item[1]))
            ambiguity = []
            if len(scored) > 1:
                ambiguity = [
                    "Multiple artifact cues matched: "
                    + ", ".join(f"{item[0]}({len(item[1])})" for item in scored)
                ]
            confidence = min(0.95, 0.55 + (0.15 * len(matches)))
            evidence = ManifestSelectionEvidence(
                manifest_id=manifest_id,
                confidence=confidence,
                matched_phrases=matches,
                ambiguity_notes=ambiguity,
            )
            return manifests[manifest_id], evidence

        fallback = self._fallback_manifest(manifests)
        evidence = ManifestSelectionEvidence(
            manifest_id=fallback.id,
            confidence=0.25,
            matched_phrases=[],
            ambiguity_notes=["No strong artifact cues matched; using preserve-first fallback."],
        )
        return fallback, evidence

    def _fallback_manifest(self, manifests: Dict[str, ArtifactManifest]) -> ArtifactManifest:
        if "unknown_freeform" in manifests:
            return manifests["unknown_freeform"]
        if manifests:
            return next(iter(manifests.values()))
        raise ValueError("No artifact manifests are available.")

    def _previous_manifest_id(self, continuation_metadata: Optional[dict]) -> Optional[str]:
        if not continuation_metadata:
            return None
        resolved_manifest = continuation_metadata.get("resolved_manifest")
        if isinstance(resolved_manifest, dict):
            manifest_id = resolved_manifest.get("id")
            if isinstance(manifest_id, str):
                return manifest_id
        manifest_selection = continuation_metadata.get("manifest_selection")
        if isinstance(manifest_selection, dict):
            manifest_id = manifest_selection.get("manifest_id")
            if isinstance(manifest_id, str):
                return manifest_id
        return None
