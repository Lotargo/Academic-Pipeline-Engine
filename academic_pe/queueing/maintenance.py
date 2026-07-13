from __future__ import annotations

from collections.abc import Callable

from celery import Celery
from sqlalchemy.orm import Session

from academic_pe.observability.config import RetentionPolicy
from academic_pe.observability.events import ObservabilityEvent
from academic_pe.observability.retention import prune_audit_events


EventRecorder = Callable[[ObservabilityEvent], None]
_TASK_NAME = "academic_pe.maintenance.prune_audit_events"
_SCHEDULE_NAME = "ape-prune-audit-events"
_MAINTENANCE_CORRELATION_ID = "maintenance_00000000"


def register_audit_pruning_task(
    app: Celery,
    session_factory: Callable[[], Session],
    policy: RetentionPolicy,
    *,
    interval_seconds: int = 86_400,
    event_recorder: EventRecorder | None = None,
) -> None:
    """Register idempotent audit pruning and the corresponding Celery Beat entry.

    The service bootstrap calls this once, then runs a maintenance-capable
    Celery worker and a single Celery Beat scheduler.  The task itself is safe
    to repeat: it only deletes rows older than the configured retention cutoff.
    """

    if interval_seconds < 3_600:
        raise ValueError("audit pruning interval must be at least one hour")

    @app.task(name=_TASK_NAME, autoretry_for=(Exception,), retry_backoff=True,
              retry_jitter=True, max_retries=5, ignore_result=True)
    def prune_expired_audit_events() -> None:
        try:
            with session_factory() as session:
                deleted = prune_audit_events(session, policy)
                session.commit()
        except Exception as exc:
            _record(
                event_recorder,
                event_type="audit.retention.prune_failed",
                severity="error",
                outcome="failure",
                details={"error_type": type(exc).__name__},
            )
            raise
        _record(
            event_recorder,
            event_type="audit.retention.pruned",
            severity="info",
            outcome="completed",
            details={"deleted_count": deleted},
        )

    schedule = dict(app.conf.beat_schedule or {})
    schedule[_SCHEDULE_NAME] = {
        "task": _TASK_NAME,
        "schedule": interval_seconds,
        "options": {"queue": "maintenance", "routing_key": "maintenance"},
    }
    app.conf.beat_schedule = schedule


def _record(
    recorder: EventRecorder | None,
    *,
    event_type: str,
    severity: str,
    outcome: str,
    details: dict[str, object],
) -> None:
    if recorder is None:
        return
    try:
        recorder(ObservabilityEvent(
            event_type=event_type,
            severity=severity,  # type: ignore[arg-type]
            correlation_id=_MAINTENANCE_CORRELATION_ID,
            source="maintenance_worker",
            outcome=outcome,
            details=details,
        ))
    except Exception:
        # A telemetry failure must not turn a successful retention run into a retry.
        return
