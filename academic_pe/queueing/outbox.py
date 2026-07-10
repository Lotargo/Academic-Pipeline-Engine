from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Callable
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from academic_pe.persistence.models import Job, JobStatus, OutboxEvent
from academic_pe.queueing.dispatchers import TaskDispatcher, TaskMessage, Workload


def create_job_with_outbox(session: Session, workspace_id: UUID, user_id: UUID,
                           kind: str, payload: dict, workload: Workload) -> Job:
    job = Job(workspace_id=workspace_id, created_by_user_id=user_id, kind=kind,
              payload=payload, status=JobStatus.PENDING)
    session.add(job)
    session.flush()
    session.add(OutboxEvent(job_id=job.id, workload=workload.value, attempts=0,
                            available_at=datetime.now(UTC)))
    session.flush()
    return job


class OutboxPublisher:
    def __init__(self, session_factory: Callable[[], Session], dispatcher: TaskDispatcher,
                 lease: timedelta = timedelta(seconds=30), max_backoff: timedelta = timedelta(minutes=5)):
        self.session_factory, self.dispatcher = session_factory, dispatcher
        self.lease, self.max_backoff = lease, max_backoff

    def publish_batch(self, limit: int = 100) -> tuple[int, int]:
        now = datetime.now(UTC)
        with self.session_factory() as session:
            events = session.scalars(select(OutboxEvent).where(
                OutboxEvent.published_at.is_(None), OutboxEvent.available_at <= now,
                or_(OutboxEvent.locked_until.is_(None), OutboxEvent.locked_until < now))
                .order_by(OutboxEvent.created_at).limit(limit).with_for_update(skip_locked=True)).all()
            for event in events:
                event.locked_until = now + self.lease
            session.commit()
            ids = [event.id for event in events]

        published = failed = 0
        for event_id in ids:
            with self.session_factory() as session:
                event = session.get(OutboxEvent, event_id)
                if event is None or event.published_at is not None:
                    continue
                try:
                    self.dispatcher.publish(TaskMessage(event.id, event.job_id, Workload(event.workload)))
                except Exception as exc:
                    event.attempts += 1
                    delay = min(2 ** min(event.attempts, 12), int(self.max_backoff.total_seconds()))
                    event.available_at = datetime.now(UTC) + timedelta(seconds=delay)
                    event.locked_until = None
                    event.last_error = f"{type(exc).__name__}: publish failed"[:500]
                    failed += 1
                else:
                    event.published_at = datetime.now(UTC)
                    event.locked_until = None
                    event.last_error = None
                    published += 1
                session.commit()
        return published, failed
