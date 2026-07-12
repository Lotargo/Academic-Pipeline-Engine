from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ConfidenceBand(str, Enum):
    DIRECT = "direct"
    DIRECT_WITH_FALLBACK = "direct_with_fallback"
    PLANNER_RECOMMENDED = "planner_recommended"
    PLANNER_REQUIRED = "planner_required"


class ArtifactCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str = Field(..., min_length=1)
    routing_score: float = Field(ge=0.0, le=1.0)
    matched_cues: list[str] = Field(default_factory=list)
    negative_cues: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class RoutingDecision(BaseModel):
    """Artifact/skill routing evidence, distinct from provider routing."""

    model_config = ConfigDict(extra="forbid")

    candidates: list[ArtifactCandidate] = Field(default_factory=list)
    selected_artifact_id: str | None = None
    top_score: float = Field(default=0.0, ge=0.0, le=1.0)
    runner_up_score: float = Field(default=0.0, ge=0.0, le=1.0)
    score_margin: float = Field(default=0.0, ge=0.0, le=1.0)
    cue_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    skill_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    conflict_score: float = Field(default=0.0, ge=0.0, le=1.0)
    channel_agreement: float = Field(default=0.0, ge=0.0, le=1.0)
    fallback_depth: int = Field(default=3, ge=0, le=3)
    active_retrieval_path: str = Field(default="local_rules_only", min_length=1)
    confidence_band: ConfidenceBand = ConfidenceBand.PLANNER_REQUIRED
    planner_required: bool = True
    reasons: list[str] = Field(default_factory=list)
    ambiguity_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_scores_and_selection(self) -> "RoutingDecision":
        if self.runner_up_score > self.top_score:
            raise ValueError("runner_up_score cannot exceed top_score")
        expected_margin = round(self.top_score - self.runner_up_score, 6)
        if abs(self.score_margin - expected_margin) > 1e-6:
            raise ValueError("score_margin must equal top_score - runner_up_score")
        candidate_ids = {candidate.artifact_id for candidate in self.candidates}
        if self.selected_artifact_id is not None and self.selected_artifact_id not in candidate_ids:
            raise ValueError("selected_artifact_id must reference a candidate")
        if self.planner_required != (self.confidence_band is ConfidenceBand.PLANNER_REQUIRED):
            raise ValueError("planner_required must agree with confidence_band")
        return self

    @classmethod
    def from_candidates(
        cls,
        candidates: list[ArtifactCandidate],
        *,
        selected_artifact_id: str | None = None,
        cue_coverage: float = 0.0,
        skill_coverage: float = 1.0,
        conflict_score: float = 0.0,
        channel_agreement: float = 1.0,
        fallback_depth: int = 3,
        active_retrieval_path: str = "local_rules_only",
        reasons: list[str] | None = None,
        ambiguity_notes: list[str] | None = None,
        explicit_override: bool = False,
    ) -> "RoutingDecision":
        ranked = sorted(candidates, key=lambda item: (-item.routing_score, item.artifact_id))
        top_score = ranked[0].routing_score if ranked else 0.0
        runner_up = ranked[1].routing_score if len(ranked) > 1 else 0.0
        margin = round(top_score - runner_up, 6)
        selected = selected_artifact_id or (ranked[0].artifact_id if ranked else None)

        if explicit_override:
            band = ConfidenceBand.DIRECT
        elif selected is None or fallback_depth >= 3 or conflict_score >= 0.5 or skill_coverage < 0.5:
            band = ConfidenceBand.PLANNER_REQUIRED
        elif margin < 0.15 or channel_agreement < 0.5:
            band = ConfidenceBand.PLANNER_REQUIRED
        elif margin < 0.30:
            band = ConfidenceBand.PLANNER_RECOMMENDED
        elif fallback_depth > 0:
            band = ConfidenceBand.DIRECT_WITH_FALLBACK
        else:
            band = ConfidenceBand.DIRECT

        return cls(
            candidates=ranked,
            selected_artifact_id=selected,
            top_score=top_score,
            runner_up_score=runner_up,
            score_margin=margin,
            cue_coverage=cue_coverage,
            skill_coverage=skill_coverage,
            conflict_score=conflict_score,
            channel_agreement=channel_agreement,
            fallback_depth=fallback_depth,
            active_retrieval_path=active_retrieval_path,
            confidence_band=band,
            planner_required=band is ConfidenceBand.PLANNER_REQUIRED,
            reasons=reasons or [],
            ambiguity_notes=ambiguity_notes or [],
        )
