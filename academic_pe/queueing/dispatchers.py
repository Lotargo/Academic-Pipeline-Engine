from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Protocol
from uuid import UUID

from celery import Celery
from kombu import Queue


class Workload(str, Enum):
    GENERATION = "generation"
    EXPORT = "export"
    RESEARCH = "research"
    MAINTENANCE = "maintenance"


@dataclass(frozen=True)
class TaskMessage:
    event_id: UUID
    job_id: UUID
    workload: Workload


class TaskDispatcher(Protocol):
    def publish(self, message: TaskMessage) -> None: ...


class LocalBackgroundDispatcher:
    """Local-first adapter around BackgroundTasks.add_task or another submit callback."""
    def __init__(self, submit: Callable[..., None], handler: Callable[[TaskMessage], None]):
        self.submit, self.handler = submit, handler

    def publish(self, message: TaskMessage) -> None:
        self.submit(self.handler, message)


def create_celery_app(broker_url: str, result_backend: str | None = None) -> Celery:
    app = Celery("academic_pe", broker=broker_url, backend=result_backend)
    app.conf.update(
        task_queues=tuple(Queue(workload.value, routing_key=workload.value) for workload in Workload),
        task_routes={"academic_pe.execute_job": {"queue": "generation"}},
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        task_acks_on_failure_or_timeout=False,
        broker_connection_retry_on_startup=True,
        worker_prefetch_multiplier=1,
    )
    return app


class CeleryTaskDispatcher:
    def __init__(self, app: Celery):
        self.app = app

    def publish(self, message: TaskMessage) -> None:
        self.app.send_task("academic_pe.execute_job", args=[str(message.event_id), str(message.job_id)],
                           queue=message.workload.value, routing_key=message.workload.value)
