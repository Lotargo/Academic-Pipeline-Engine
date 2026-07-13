from __future__ import annotations

from datetime import UTC, datetime
from typing import Callable, Mapping
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from celery import Celery

from academic_pe.observability.events import ObservabilityEvent
from academic_pe.observability.runtime import correlation_context
from academic_pe.persistence.models import Job, OutboxEvent, WorkerDelivery
from academic_pe.queueing.dispatchers import Workload


EventRecorder = Callable[[ObservabilityEvent], None]


def execute_once(session: Session, event_id: UUID, job_id: UUID, consumer: str,
                 handler: Callable[[Session, UUID], None]) -> bool:
    existing = session.scalar(select(WorkerDelivery).where(
        WorkerDelivery.event_id == event_id, WorkerDelivery.consumer == consumer))
    if existing is not None:
        return False
    handler(session, job_id)
    session.add(WorkerDelivery(event_id=event_id, job_id=job_id, consumer=consumer,
                               completed_at=datetime.now(UTC)))
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return False
    return True


def execute_worker_delivery(
    session: Session,
    event_id: UUID,
    job_id: UUID,
    handlers: Mapping[Workload, Callable[[Session, UUID], None]],
    *,
    event_recorder: EventRecorder | None = None,
) -> bool:
    """Execute one broker delivery and emit a redacted failure signal if it fails."""

    job = session.get(Job, job_id)
    payload = job.payload if job is not None and isinstance(job.payload, dict) else {}
    correlation_id = payload.get("correlation_id") if isinstance(payload.get("correlation_id"), str) else None
    with correlation_context(correlation_id) as bound_correlation_id:
        event: OutboxEvent | None = None
        try:
            event = session.get(OutboxEvent, event_id)
            if event is None or event.job_id != job_id:
                raise ValueError("outbox event does not match job")
            if job is None:
                raise ValueError("job does not exist")
            workload = Workload(event.workload)
            return execute_once(session, event_id, job_id, f"{workload.value}-worker", handlers[workload])
        except Exception as exc:
            _record_failure(
                event_recorder,
                correlation_id=bound_correlation_id,
                job_id=job_id,
                workspace_id=job.workspace_id if job is not None else None,
                workload=event.workload if event is not None else "unknown",
                error_type=type(exc).__name__,
            )
            raise


def _record_failure(
    recorder: EventRecorder | None,
    *,
    correlation_id: str,
    job_id: UUID,
    workspace_id: UUID | None,
    workload: str,
    error_type: str,
) -> None:
    if recorder is None:
        return
    try:
        recorder(ObservabilityEvent(
            event_type="worker.delivery.failed",
            severity="error",
            correlation_id=correlation_id,
            source="queue_worker",
            outcome="failure",
            job_id=str(job_id),
            workspace_id=str(workspace_id) if workspace_id is not None else None,
            details={"workload": workload, "error_type": error_type},
        ))
    except Exception:
        # Telemetry must never suppress Celery retry/error handling.
        return


def register_worker_task(app: Celery, session_factory: Callable[[], Session],
                         handlers: Mapping[Workload, Callable[[Session, UUID], None]],
                         *, event_recorder: EventRecorder | None = None) -> None:
    @app.task(name="academic_pe.execute_job", bind=True, autoretry_for=(Exception,),
              retry_backoff=True, retry_jitter=True, max_retries=5)
    def execute_job(self, event_id: str, job_id: str) -> bool:
        event_uuid, job_uuid = UUID(event_id), UUID(job_id)
        with session_factory() as session:
            return execute_worker_delivery(
                session, event_uuid, job_uuid, handlers, event_recorder=event_recorder)
