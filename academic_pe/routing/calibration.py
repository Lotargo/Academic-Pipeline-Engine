from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field


class ConfidenceObservation(BaseModel):
    """One labelled routing outcome used to fit the confidence mapping."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    routing_score: float = Field(ge=0.0, le=1.0)
    correct: bool


class RoutingConfidenceCalibrator(BaseModel):
    """Small dependency-free isotonic calibrator for routing scores.

    A monotonic step function is intentionally used instead of treating a raw
    RRF or lexical score as probability.  It is serializable, deterministic and
    can be re-fitted by the offline benchmark without introducing a runtime ML
    dependency.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = "routing-isotonic-v1"
    score_thresholds: list[float] = Field(default_factory=list)
    calibrated_values: list[float] = Field(default_factory=list)
    observation_count: int = Field(default=0, ge=0)

    @classmethod
    def fit(cls, observations: Iterable[ConfidenceObservation]) -> "RoutingConfidenceCalibrator":
        grouped: dict[float, list[int]] = {}
        for item in observations:
            grouped.setdefault(round(item.routing_score, 6), []).append(int(item.correct))
        if not grouped:
            return cls()

        # Pool-adjacent-violators algorithm: merge decreasing empirical rates
        # until the calibrated mapping is monotone in the raw routing score.
        blocks: list[dict[str, float | int]] = []
        for score, labels in sorted(grouped.items()):
            blocks.append({"start": score, "end": score, "positives": sum(labels), "count": len(labels)})
            while len(blocks) >= 2 and _block_value(blocks[-2]) > _block_value(blocks[-1]):
                right = blocks.pop()
                left = blocks.pop()
                blocks.append({
                    "start": left["start"],
                    "end": right["end"],
                    "positives": int(left["positives"]) + int(right["positives"]),
                    "count": int(left["count"]) + int(right["count"]),
                })
        return cls(
            score_thresholds=[round(float(block["end"]), 6) for block in blocks],
            calibrated_values=[round(_block_value(block), 6) for block in blocks],
            observation_count=sum(len(labels) for labels in grouped.values()),
        )

    def predict(self, routing_score: float) -> float | None:
        if not self.score_thresholds:
            return None
        bounded = min(1.0, max(0.0, routing_score))
        for threshold, value in zip(self.score_thresholds, self.calibrated_values, strict=True):
            if bounded <= threshold:
                return value
        return self.calibrated_values[-1]


def _block_value(block: dict[str, float | int]) -> float:
    return int(block["positives"]) / int(block["count"])
