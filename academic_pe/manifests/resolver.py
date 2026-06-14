from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Optional

from academic_pe.contracts.compiler import compile_artifact_contract
from academic_pe.contracts.models import ArtifactContract
from academic_pe.contracts.sexpr import render_contract_sexpr
from academic_pe.manifests.evidence import ManifestSelectionEvidence
from academic_pe.manifests.fallback import fallback_evidence, select_fallback_manifest
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
            "decision_summary": self.decision_summary(),
        }

    def decision_summary(self) -> dict:
        artifact_label = self.contract.artifact.replace("_", " ")
        mode_label = self.contract.execution_mode
        matched = list(self.evidence.matched_phrases)
        ambiguity = list(self.evidence.ambiguity_notes[:2])
        if matched:
            reason = f"Matched artifact cues: {', '.join(matched[:4])}."
        else:
            reason = "No strong artifact cues matched; using preserve-first fallback."
        if ambiguity and "Inherited artifact behavior" in ambiguity[0]:
            reason = "Inherited artifact behavior from continuation metadata."
        elif ambiguity and "legacy continuation metadata" in ambiguity[0]:
            reason = "Inferred artifact behavior from legacy continuation metadata."

        return {
            "selected_manifest": self.manifest.id,
            "manifest_version": self.manifest.version,
            "artifact": self.contract.artifact,
            "confidence": round(self.evidence.confidence, 2),
            "matched_phrases": matched,
            "mode": mode_label,
            "summary": f"{reason} Preserving {artifact_label} behavior in {mode_label} mode.",
            "ambiguity_notes": ambiguity,
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
        execution_mode: Optional[str] = None,
        language: str = "auto",
        mode: str = "new",
        continuation_metadata: Optional[dict] = None,
        artifact_override: Optional[str] = None,
    ) -> ResolvedArtifactManifest:
        manifests = self._load_manifests()

        if artifact_override and artifact_override in manifests:
            manifest = manifests[artifact_override]
            evidence = ManifestSelectionEvidence(
                manifest_id=manifest.id,
                confidence=1.0,
                matched_phrases=["user override"],
                ambiguity_notes=[f"User explicitly selected artifact type: {manifest.id}"],
            )
        else:
            previous_manifest_id = self._previous_manifest_id(continuation_metadata)
            current_manifest, current_evidence = self._select_manifest(manifests, topic, instructions)
            if current_evidence.matched_phrases and (
                previous_manifest_id is None or current_manifest.id != previous_manifest_id
            ):
                manifest = current_manifest
                evidence = current_evidence
            else:
                manifest = None
                evidence = None

            if manifest is None and previous_manifest_id and previous_manifest_id in manifests:
                manifest = manifests[previous_manifest_id]
                evidence = ManifestSelectionEvidence(
                    manifest_id=manifest.id,
                    confidence=0.9,
                    matched_phrases=["previous resolved manifest"],
                    ambiguity_notes=["Inherited artifact behavior from continuation metadata."],
                )

            if manifest is None:
                legacy_text = self._legacy_continuation_text(continuation_metadata)
                if legacy_text:
                    legacy_manifest, legacy_evidence = self._select_manifest(manifests, "", legacy_text)
                    if legacy_evidence.matched_phrases:
                        manifest = legacy_manifest
                        evidence = ManifestSelectionEvidence(
                            manifest_id=legacy_manifest.id,
                            confidence=min(0.75, legacy_evidence.confidence),
                            matched_phrases=legacy_evidence.matched_phrases,
                            ambiguity_notes=[
                                "Inferred artifact behavior from legacy continuation metadata.",
                                *legacy_evidence.ambiguity_notes,
                            ],
                        )

            if manifest is None or evidence is None:
                manifest = current_manifest
                evidence = current_evidence

        extra_reqs = {}
        if mode == "continuation" and evidence.confidence < 0.65:
            extra_reqs["preserve_style_and_avoid_new_structure"] = True

        resolved_execution_mode = execution_mode or ("academic" if academic_mode else "standard")
        contract = compile_artifact_contract(
            manifest,
            language=language,
            mode=mode,
            execution_mode=resolved_execution_mode,
            extra_requirements=extra_reqs,
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
        return fallback, fallback_evidence(fallback)

    def _fallback_manifest(self, manifests: Dict[str, ArtifactManifest]) -> ArtifactManifest:
        return select_fallback_manifest(manifests)

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

    def _legacy_continuation_text(self, continuation_metadata: Optional[dict]) -> str:
        if not continuation_metadata:
            return ""

        parts: list[str] = []
        for key in ["previous_prompt", "topic", "instructions", "document_plan"]:
            value = continuation_metadata.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(value.strip())

        runtime_template = continuation_metadata.get("runtime_template")
        if isinstance(runtime_template, dict):
            for key in ["name", "category"]:
                value = runtime_template.get(key)
                if isinstance(value, str) and value.strip():
                    parts.append(value.strip())
            sections = runtime_template.get("sections")
            if isinstance(sections, list):
                for section in sections:
                    if not isinstance(section, dict):
                        continue
                    for key in ["name", "title", "instruction"]:
                        value = section.get(key)
                        if isinstance(value, str) and value.strip():
                            parts.append(value.strip())

        context = continuation_metadata.get("context")
        if isinstance(context, dict):
            for key, value in context.items():
                if key == "document_plan":
                    continue
                if isinstance(value, str) and value.strip():
                    parts.append(value.strip())

        return "\n".join(parts)[:12000]
