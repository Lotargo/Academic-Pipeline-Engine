import logging
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from academic_pe.observability import (
    CorrelationIdMiddleware,
    ObservabilityEvent,
    StructuredEventFormatter,
    TelemetryStore,
    get_correlation_id,
    RetentionPolicy,
    prune_audit_events,
    safe_audit_metadata,
)
from academic_pe.persistence.base import Base
from academic_pe.persistence.models import AuditEvent
from academic_pe.secrets.redaction import REDACTED


def _app_with_observability():
    app = FastAPI()
    telemetry = TelemetryStore(max_events=10, retention_seconds=60)
    app.add_middleware(CorrelationIdMiddleware, telemetry=telemetry)

    @app.get("/healthz")
    def healthz(request: Request):
        return {"correlation_id": request.state.correlation_id, "context": get_correlation_id()}

    @app.get("/jobs/{job_id}")
    def job(job_id: str):
        return {"job_id": job_id, "context": get_correlation_id()}

    @app.get("/metrics")
    def metrics():
        return telemetry.prometheus_metrics()

    return app, telemetry


def test_correlation_middleware_validates_header_and_uses_route_templates_for_metrics():
    app, telemetry = _app_with_observability()
    client = TestClient(app)

    accepted = client.get("/jobs/a-sensitive-id", headers={"X-Correlation-ID": "trace_12345678"})
    rejected = client.get("/healthz", headers={"X-Correlation-ID": "Bearer unsafe value"})

    assert accepted.headers["X-Correlation-ID"] == "trace_12345678"
    assert rejected.headers["X-Correlation-ID"] != "Bearer unsafe value"
    assert accepted.json()["context"] == "trace_12345678"
    metrics = telemetry.prometheus_metrics()
    assert 'route="/jobs/{job_id}"' in metrics
    assert "a-sensitive-id" not in metrics
    assert telemetry.snapshot()["http_requests"] == 2


def test_event_schema_audit_metadata_and_structured_logs_redact_secrets():
    event = ObservabilityEvent(
        event_type="provider.request.failed",
        correlation_id="trace_12345678",
        source="provider",
        details={"api_key": "plain-secret", "nested": {"token": "also-secret"}},
    )
    audit = safe_audit_metadata("trace_12345678", authorization="Bearer abc", label="safe")
    record = logging.LogRecord(
        name="ape.test", level=logging.ERROR, pathname=__file__, lineno=1,
        msg="token=raw-token", args=(), exc_info=None,
    )
    record.correlation_id = "trace_12345678"
    rendered = StructuredEventFormatter().format(record)

    assert event.details["api_key"] == REDACTED
    assert event.details["nested"]["token"] == REDACTED
    assert audit["authorization"] == REDACTED
    assert audit["correlation_id"] == "trace_12345678"
    assert "raw-token" not in rendered
    assert REDACTED in rendered


def test_server_health_and_metrics_are_safe_and_return_correlation_id():
    from academic_pe.server import app

    client = TestClient(app)
    response = client.get("/healthz", headers={"X-Correlation-ID": "trace_87654321"})
    readiness = client.get("/readyz")
    metrics = client.get("/metrics")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "correlation_id": "trace_87654321"}
    assert readiness.json()["checks"] == {"api": "ok"}
    assert "APE_DATABASE" not in response.text
    assert "api-key" not in metrics.text.casefold()
    assert metrics.headers["content-type"].startswith("text/plain")


def test_retention_prunes_only_expired_audit_events_and_telemetry_is_bounded():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(engine, expire_on_commit=False)()
    now = datetime.now(UTC)
    session.add_all([
        AuditEvent(event_type="admin.old", metadata_json={}, created_at=now - timedelta(days=366)),
        AuditEvent(event_type="admin.recent", metadata_json={}, created_at=now - timedelta(days=2)),
    ])
    session.commit()

    assert prune_audit_events(session, RetentionPolicy(audit_event_days=365), now=now) == 1
    session.commit()
    assert [item.event_type for item in session.scalars(select(AuditEvent)).all()] == ["admin.recent"]

    telemetry = TelemetryStore(max_events=2, retention_seconds=60)
    telemetry.record(ObservabilityEvent(
        event_type="test.expired", correlation_id="trace_12345678", source="test",
        occurred_at=now - timedelta(seconds=61),
    ))
    assert telemetry.snapshot()["events_retained"] == 0
