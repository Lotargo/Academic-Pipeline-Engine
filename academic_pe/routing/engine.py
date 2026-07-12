from __future__ import annotations

from pathlib import Path

from academic_pe.routing.calibration import RoutingConfidenceCalibrator
from academic_pe.routing.evidence import RoutingChannelEvidence, RoutingEvidenceChannel
from academic_pe.routing.index import RoutingIndex, RoutingQuery, RoutingSearchResult
from academic_pe.routing.models import ArtifactCandidate, RoutingDecision
from academic_pe.routing.cards import RoutingEntityType


class RoutingEngine:
    """Build the public routing decision from adapter-returned evidence.

    The engine does not invent channel data.  It simply translates the exact
    per-card evidence emitted by the selected ``RoutingIndex`` into immutable
    artifact candidates and confidence inputs.
    """

    def __init__(
        self,
        index: RoutingIndex,
        *,
        confidence_calibrator: RoutingConfidenceCalibrator | None = None,
    ) -> None:
        self._index = index
        self._confidence_calibrator = confidence_calibrator

    @classmethod
    def with_default_calibration(
        cls,
        index: RoutingIndex,
        *,
        calibration_path: str | Path | None = None,
    ) -> "RoutingEngine":
        """Build an engine with the checked-in calibration profile when present.

        Missing files intentionally produce an uncalibrated engine so local-first
        use never needs a deployment artifact to route safely.
        """

        calibrator = (
            RoutingConfidenceCalibrator.from_yaml(calibration_path)
            if calibration_path else RoutingConfidenceCalibrator.from_yaml()
        )
        return cls(index, confidence_calibrator=calibrator if calibrator.observation_count else None)

    async def decide(
        self,
        query: RoutingQuery,
        *,
        explicit_artifact_override: str | None = None,
    ) -> RoutingDecision:
        results = await self._index.search(query)
        artifact_results = [item for item in results if item.card.entity_type is RoutingEntityType.ARTIFACT]
        candidates = [self._candidate_from_result(item) for item in artifact_results]
        if explicit_artifact_override and explicit_artifact_override not in {item.artifact_id for item in candidates}:
            candidates.append(ArtifactCandidate(
                artifact_id=explicit_artifact_override,
                routing_score=1.0,
                matched_cues=["user override"],
                reasons=["explicit artifact override"],
            ))
        selected = explicit_artifact_override or (candidates[0].artifact_id if candidates else None)
        top = artifact_results[0] if artifact_results else None
        all_evidence = [evidence for candidate in candidates for evidence in candidate.channel_evidence]
        calibrated = self._confidence_calibrator.predict(top.score) if top and self._confidence_calibrator else None
        reasons = _decision_reasons(top, selected)
        return RoutingDecision.from_candidates(
            candidates,
            selected_artifact_id=selected,
            cue_coverage=_cue_coverage(top, query.text) if top else 0.0,
            skill_coverage=1.0,
            conflict_score=_conflict_score(top),
            channel_agreement=_channel_agreement(top),
            fallback_depth=_fallback_depth(top),
            active_retrieval_path=_retrieval_path(top),
            channel_evidence=all_evidence,
            calibrated_confidence=calibrated,
            calibration_version=self._confidence_calibrator.version if calibrated is not None else None,
            reasons=reasons,
            ambiguity_notes=[],
            explicit_override=explicit_artifact_override is not None,
        )

    @staticmethod
    def _candidate_from_result(result: RoutingSearchResult) -> ArtifactCandidate:
        return ArtifactCandidate(
            artifact_id=result.card.entity_id,
            routing_score=result.score,
            matched_cues=[*result.matched_terms, *result.matched_positive_examples],
            negative_cues=list(result.matched_negative_examples),
            reasons=[
                f"{evidence.channel.value} rank {evidence.rank}"
                if evidence.rank is not None
                else evidence.channel.value
                for evidence in result.channel_evidence
            ],
            channel_evidence=list(result.channel_evidence),
        )


def _retrieval_evidence(result: RoutingSearchResult | None) -> list[RoutingChannelEvidence]:
    return [
        item for item in (result.channel_evidence if result else [])
        if item.channel not in {RoutingEvidenceChannel.RRF, RoutingEvidenceChannel.GRAPH_PENALTY}
    ]


def _retrieval_path(result: RoutingSearchResult | None) -> str:
    channels = {item.channel for item in _retrieval_evidence(result)}
    if RoutingEvidenceChannel.QDRANT_E5 in channels and RoutingEvidenceChannel.QDRANT_BM25 in channels:
        return "e5_bm25_colbert" if RoutingEvidenceChannel.COLBERT in channels else "e5_bm25"
    if RoutingEvidenceChannel.QDRANT_BM25 in channels:
        return "bm25_local_rules"
    return "local_rules_only"


def _fallback_depth(result: RoutingSearchResult | None) -> int:
    path = _retrieval_path(result)
    return {"e5_bm25": 1, "e5_bm25_colbert": 1, "bm25_local_rules": 2}.get(path, 3)


def _channel_agreement(result: RoutingSearchResult | None) -> float:
    channels = {item.channel for item in _retrieval_evidence(result)}
    hybrid_channels = {
        RoutingEvidenceChannel.QDRANT_E5,
        RoutingEvidenceChannel.QDRANT_BM25,
        RoutingEvidenceChannel.COLBERT,
    }
    active = channels.intersection(hybrid_channels)
    if len(active) >= 2:
        return 1.0
    if active:
        return 0.5
    return 1.0 if RoutingEvidenceChannel.LEXICAL_RULES in channels else 0.0


def _conflict_score(result: RoutingSearchResult | None) -> float:
    if result is None:
        return 0.0
    return min(1.0, round(sum(
        -item.contribution
        for item in result.channel_evidence
        if item.channel is RoutingEvidenceChannel.GRAPH_PENALTY and item.contribution < 0
    ), 6))


def _cue_coverage(result: RoutingSearchResult, text: str) -> float:
    query_terms = {token for token in text.casefold().split() if token}
    cues = set(result.matched_terms).union(result.matched_positive_examples)
    return min(1.0, len(cues) / max(1, len(query_terms)))


def _decision_reasons(result: RoutingSearchResult | None, selected: str | None) -> list[str]:
    if result is None or selected is None:
        return ["no artifact candidates were returned by the active routing index"]
    channels = ", ".join(item.channel.value for item in _retrieval_evidence(result))
    return [f"selected {selected} from observed routing channels: {channels}"]
