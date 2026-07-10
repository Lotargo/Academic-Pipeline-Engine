from __future__ import annotations

from datetime import UTC, datetime
from typing import Callable, Mapping
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from celery import Celery

from academic_pe.persistence.models import WorkerDelivery
from academic_pe.persistence.models import OutboxEvent
from academic_pe.queueing.dispatchers import Workload


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


def register_worker_task(app: Celery, session_factory: Callable[[], Session],
                         handlers: Mapping[Workload, Callable[[Session, UUID], None]]) -> None:
    @app.task(name="academic_pe.execute_job", bind=True, autoretry_for=(Exception,),
              retry_backoff=True, retry_jitter=True, max_retries=5)
    def execute_job(self, event_id: str, job_id: str) -> bool:
        event_uuid, job_uuid = UUID(event_id), UUID(job_id)
        with session_factory() as session:
            event = session.get(OutboxEvent, event_uuid)
            if event is None or event.job_id != job_uuid:
                raise ValueError("outbox event does not match job")
            workload = Workload(event.workload)
            handler = handlers[workload]
            return execute_once(session, event_uuid, job_uuid,
                                f"{workload.value}-worker", handler)
