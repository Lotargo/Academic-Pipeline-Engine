import asyncio

import httpx

from academic_pe.evaluation import run_routing_benchmark
from academic_pe.routing import (
    ConfidenceObservation,
    InMemoryRoutingIndex,
    QdrantRoutingIndex,
    RetrievalCard,
    RoutingConfidenceCalibrator,
    RoutingEntityType,
    RoutingQuery,
)


def _run(awaitable):
    return asyncio.run(awaitable)


def _card():
    return RetrievalCard(
        entity_type=RoutingEntityType.ARTIFACT,
        entity_id="report",
        version=1,
        title="Report",
        descriptions={"en": ["Analytical report with findings and evidence."]},
        positive_examples=["evidence report"],
    )


def test_isotonic_confidence_calibration_is_monotone_and_serializable():
    calibrator = RoutingConfidenceCalibrator.fit([
        ConfidenceObservation(routing_score=0.2, correct=True),
        ConfidenceObservation(routing_score=0.4, correct=False),
        ConfidenceObservation(routing_score=0.8, correct=True),
    ])

    predictions = [calibrator.predict(score) for score in (0.0, 0.2, 0.4, 0.8, 1.0)]
    assert predictions == sorted(predictions)
    assert calibrator.observation_count == 3
    assert RoutingConfidenceCalibrator.model_validate(calibrator.model_dump()) == calibrator


def test_qdrant_unavailable_delegates_to_configured_local_fallback():
    fallback = InMemoryRoutingIndex()
    _run(fallback.upsert([_card()]))

    def offline(_request):
        raise httpx.ConnectError("offline")

    index = QdrantRoutingIndex(
        url="https://qdrant.example.test",
        collection_name="routing_knowledge",
        fallback_index=fallback,
        transport=httpx.MockTransport(offline),
    )
    results = _run(index.search(RoutingQuery(text="evidence report")))
    _run(index.aclose())

    assert [item.card.entity_id for item in results] == ["report"]
    assert results[0].channel_evidence[0].channel.value == "lexical_rules"


def test_core14_routing_benchmark_fits_a_reusable_calibrator():
    report = _run(run_routing_benchmark())

    assert len(report.cases) >= 12
    assert report.confidence_calibrator.observation_count == len(report.cases)
    assert report.artifact_top_one_accuracy >= 0.75
    assert report.planner_escalation_accuracy == 1.0
    assert report.confidence_brier_score is not None
