from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from time import perf_counter
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from academic_pe.manifests.loader import ArtifactManifestLoader
from academic_pe.routing.calibration import ConfidenceObservation, RoutingConfidenceCalibrator
from academic_pe.routing.cards import RoutingEntityType, artifact_retrieval_cards
from academic_pe.routing.engine import RoutingEngine
from academic_pe.routing.index import InMemoryRoutingIndex, RoutingIndex, RoutingQuery
from academic_pe.routing.models import RoutingDecision


DEFAULT_ROUTING_BENCHMARK_PATH = Path("config/routing_benchmark.yaml")


class RoutingBenchmarkCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    expected_artifact_id: str | None = None
    planner_required: bool = False
    split: Literal["calibration", "holdout"] = "holdout"
    artifact_override: str | None = None


class RoutingBenchmarkCaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    expected_artifact_id: str | None = None
    selected_artifact_id: str | None = None
    top_three_artifact_ids: list[str] = Field(default_factory=list)
    correct_top_one: bool
    correct_top_three: bool
    expected_planner_required: bool
    actual_planner_required: bool
    routing_score: float = Field(ge=0.0, le=1.0)
    calibrated_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    latency_ms: float = Field(ge=0.0)


class RoutingBenchmarkReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_path: str
    cases: list[RoutingBenchmarkCaseResult]
    artifact_top_one_accuracy: float = Field(ge=0.0, le=1.0)
    artifact_top_three_recall: float = Field(ge=0.0, le=1.0)
    planner_escalation_accuracy: float = Field(ge=0.0, le=1.0)
    mean_latency_ms: float = Field(ge=0.0)
    confidence_brier_score: float | None = Field(default=None, ge=0.0)
    confidence_calibrator: RoutingConfidenceCalibrator
    calibration_case_count: int = Field(ge=1)
    holdout_case_count: int = Field(ge=1)
    retrieval_path_counts: dict[str, int] = Field(default_factory=dict)


def load_routing_benchmark_cases(
    path: str | Path = DEFAULT_ROUTING_BENCHMARK_PATH,
) -> list[RoutingBenchmarkCase]:
    file_path = Path(path)
    raw = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
    return [RoutingBenchmarkCase.model_validate(item) for item in raw.get("cases", [])]


async def run_routing_benchmark(
    cases: Sequence[RoutingBenchmarkCase] | None = None,
    *,
    dataset_path: str | Path = DEFAULT_ROUTING_BENCHMARK_PATH,
    index: RoutingIndex | None = None,
) -> RoutingBenchmarkReport:
    selected_cases = list(cases) if cases is not None else load_routing_benchmark_cases(dataset_path)
    if not selected_cases:
        raise ValueError("routing benchmark requires at least one case")
    active_index = index
    if active_index is None:
        active_index = InMemoryRoutingIndex()
        manifests = ArtifactManifestLoader("config/artifact_manifests.yaml").load()
        await active_index.upsert(artifact_retrieval_cards(manifests.values()))
    raw_engine = RoutingEngine(active_index)

    raw_outcomes: list[tuple[RoutingBenchmarkCase, RoutingDecision, float]] = []
    observations: list[ConfidenceObservation] = []
    for case in selected_cases:
        started = perf_counter()
        decision = await raw_engine.decide(RoutingQuery(
            text=case.text,
            entity_types={RoutingEntityType.ARTIFACT},
            top_k=3,
        ), explicit_artifact_override=case.artifact_override)
        elapsed = (perf_counter() - started) * 1000
        correct = decision.selected_artifact_id == case.expected_artifact_id
        observations.append(ConfidenceObservation(routing_score=decision.top_score, correct=correct))
        raw_outcomes.append((case, decision, elapsed))

    calibration_indices = [
        index for index, (case, _, _) in enumerate(raw_outcomes)
        if case.split == "calibration"
    ]
    holdout_indices = [
        index for index, (case, _, _) in enumerate(raw_outcomes)
        if case.split == "holdout"
    ]
    if not calibration_indices or not holdout_indices:
        raise ValueError("routing benchmark requires both calibration and holdout cases")
    calibrator = RoutingConfidenceCalibrator.fit(observations[index] for index in calibration_indices)
    results = [
        _case_result(case, decision, elapsed, calibrator)
        for case, decision, elapsed in raw_outcomes
    ]
    total = len(results)
    top_one = sum(result.correct_top_one for result in results) / total
    top_three = sum(result.correct_top_three for result in results) / total
    planner_accuracy = sum(
        result.actual_planner_required == result.expected_planner_required
        for result in results
    ) / total
    # This profile is fitted strictly on the calibration split.  The Brier
    # metric below is therefore a true holdout measurement, not an optimistic
    # leave-one-out approximation over the same small corpus.
    brier_terms = [
        (float(result.calibrated_confidence) - float(result.correct_top_one)) ** 2
        for (case, _, _), result in zip(raw_outcomes, results, strict=True)
        if case.split == "holdout" and result.calibrated_confidence is not None
    ]
    brier = sum(brier_terms) / len(brier_terms) if brier_terms else None
    return RoutingBenchmarkReport(
        dataset_path=str(dataset_path),
        cases=results,
        artifact_top_one_accuracy=round(top_one, 6),
        artifact_top_three_recall=round(top_three, 6),
        planner_escalation_accuracy=round(planner_accuracy, 6),
        mean_latency_ms=round(sum(result.latency_ms for result in results) / total, 6),
        confidence_brier_score=round(brier, 6) if brier is not None else None,
        confidence_calibrator=calibrator,
        calibration_case_count=len(calibration_indices),
        holdout_case_count=len(holdout_indices),
        retrieval_path_counts={
            path: sum(
                1
                for _, decision, _ in raw_outcomes
                if decision.active_retrieval_path == path
            )
            for path in sorted({decision.active_retrieval_path for _, decision, _ in raw_outcomes})
        },
    )


def _case_result(
    case: RoutingBenchmarkCase,
    decision: RoutingDecision,
    elapsed: float,
    calibrator: RoutingConfidenceCalibrator,
) -> RoutingBenchmarkCaseResult:
    top_three = [candidate.artifact_id for candidate in decision.candidates[:3]]
    correct_top_one = decision.selected_artifact_id == case.expected_artifact_id
    return RoutingBenchmarkCaseResult(
        case_id=case.case_id,
        expected_artifact_id=case.expected_artifact_id,
        selected_artifact_id=decision.selected_artifact_id,
        top_three_artifact_ids=top_three,
        correct_top_one=correct_top_one,
        correct_top_three=case.expected_artifact_id in top_three,
        expected_planner_required=case.planner_required,
        actual_planner_required=decision.planner_required,
        routing_score=decision.top_score,
        calibrated_confidence=calibrator.predict(decision.top_score),
        latency_ms=round(elapsed, 6),
    )
