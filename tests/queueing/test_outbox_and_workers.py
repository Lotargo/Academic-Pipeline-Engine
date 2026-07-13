from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from academic_pe.persistence.base import Base
from academic_pe.persistence.models import (AuditEvent, Job, JobEvent, Membership, MembershipRole,
    Organization, OrganizationKind, OutboxEvent, User, WorkerDelivery, Workspace)
from academic_pe.observability import RetentionPolicy
from academic_pe.queueing.dispatchers import (LocalBackgroundDispatcher, TaskMessage,
    Workload, create_celery_app)
from academic_pe.queueing.maintenance import register_audit_pruning_task
from academic_pe.queueing.outbox import OutboxPublisher, create_job_with_outbox
from academic_pe.observability import TelemetryStore, get_correlation_id
from academic_pe.queueing.worker import execute_once, execute_worker_delivery, register_worker_task


def setup():
    engine = create_engine("sqlite://", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as session:
        user = User(email="user@example.com", password_hash="password-reset-required")
        session.add(user); session.flush()
        organization = Organization(owner_user_id=user.id, kind=OrganizationKind.PERSONAL, name="Personal")
        session.add(organization); session.flush()
        workspace = Workspace(organization_id=organization.id, name="Personal")
        session.add(workspace); session.flush()
        session.add(Membership(workspace_id=workspace.id, user_id=user.id, membership_role=MembershipRole.OWNER))
        session.commit()
        return factory, user.id, workspace.id


class RecordingDispatcher:
    def __init__(self, failures=0):
        self.failures, self.messages = failures, []

    def publish(self, message):
        if self.failures:
            self.failures -= 1
            raise ConnectionError("broker unavailable with secret=must-not-leak")
        self.messages.append(message)


def test_job_and_outbox_share_transaction_and_message_contains_only_ids():
    factory, user_id, workspace_id = setup()
    with factory() as session:
        create_job_with_outbox(session, workspace_id, user_id, "generation",
                               {"credential_id": "db-only"}, Workload.GENERATION)
        session.rollback()
        assert session.scalar(select(Job)) is None
        assert session.scalar(select(OutboxEvent)) is None
        job = create_job_with_outbox(session, workspace_id, user_id, "generation",
                                     {"credential_id": "db-only"}, Workload.GENERATION)
        session.commit()
    dispatcher = RecordingDispatcher()
    assert OutboxPublisher(factory, dispatcher).publish_batch() == (1, 0)
    message = dispatcher.messages[0]
    assert message.job_id == job.id
    assert set(message.__dict__) == {"event_id", "job_id", "workload"}
    assert "db-only" not in repr(message)


def test_broker_outage_keeps_outbox_and_retry_publishes_once():
    factory, user_id, workspace_id = setup()
    with factory() as session:
        create_job_with_outbox(session, workspace_id, user_id, "export", {}, Workload.EXPORT)
        session.commit()
    dispatcher = RecordingDispatcher(failures=1)
    publisher = OutboxPublisher(factory, dispatcher)
    assert publisher.publish_batch() == (0, 1)
    with factory() as session:
        event = session.scalar(select(OutboxEvent))
        assert event.published_at is None and event.attempts == 1
        assert "must-not-leak" not in event.last_error
        event.available_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
    assert publisher.publish_batch() == (1, 0)
    assert publisher.publish_batch() == (0, 0)
    assert len(dispatcher.messages) == 1


def test_worker_redelivery_is_idempotent_and_local_dispatcher_is_preserved():
    factory, user_id, workspace_id = setup()
    with factory() as session:
        job = create_job_with_outbox(session, workspace_id, user_id, "research", {}, Workload.RESEARCH)
        session.commit()
        event = session.scalar(select(OutboxEvent))
        def handler(unit, job_id):
            unit.add(JobEvent(job_id=job_id, event_type="domain.side_effect", data={}))
        assert execute_once(session, event.id, job.id, "research-worker", handler)
        assert not execute_once(session, event.id, job.id, "research-worker", handler)
        assert len(session.scalars(select(JobEvent)).all()) == 1
        assert len(session.scalars(select(WorkerDelivery)).all()) == 1
    submitted = []
    local = LocalBackgroundDispatcher(lambda fn, msg: submitted.append((fn, msg)), lambda _: None)
    local.publish(TaskMessage(event.id, job.id, Workload.RESEARCH))
    assert submitted[0][1].workload == Workload.RESEARCH


def test_celery_declares_all_workload_queues_and_reliable_ack_policy():
    app = create_celery_app("amqp://guest:guest@localhost//")
    factory, _, _ = setup()
    register_worker_task(app, factory, {item: (lambda session, job_id: None) for item in Workload})
    assert {queue.name for queue in app.conf.task_queues} == {item.value for item in Workload}
    assert app.conf.task_acks_late is True
    assert app.conf.task_reject_on_worker_lost is True
    assert app.conf.worker_prefetch_multiplier == 1
    assert "academic_pe.execute_job" in app.tasks


def test_worker_failure_is_redacted_and_uses_job_correlation_id():
    factory, user_id, workspace_id = setup()
    with factory() as session:
        job = create_job_with_outbox(
            session, workspace_id, user_id, "research",
            {"correlation_id": "trace_12345678", "credential": "must-not-leak"}, Workload.RESEARCH,
        )
        session.commit()
        event = session.scalar(select(OutboxEvent))
        telemetry = TelemetryStore()

        def failing_handler(_session, _job_id):
            assert get_correlation_id() == "trace_12345678"
            raise RuntimeError("worker failure secret=must-not-leak")

        with pytest.raises(RuntimeError, match="worker failure"):
            execute_worker_delivery(
                session, event.id, job.id,
                {item: failing_handler for item in Workload}, event_recorder=telemetry.record,
            )

    recorded = telemetry.recent_events()
    assert len(recorded) == 1
    failure = recorded[0]
    assert failure.event_type == "worker.delivery.failed"
    assert failure.correlation_id == "trace_12345678"
    assert failure.job_id == str(job.id)
    assert failure.workspace_id == str(workspace_id)
    assert failure.details == {"workload": "research", "error_type": "RuntimeError"}
    assert "must-not-leak" not in str(failure.model_dump())
    assert 'ape_observability_events_total{event_type="worker.delivery.failed"' in telemetry.prometheus_metrics()


def test_audit_pruning_is_scheduled_on_maintenance_queue_and_is_idempotent():
    factory, _, _ = setup()
    app = create_celery_app("amqp://guest:guest@localhost//")
    with factory() as session:
        now = datetime.now(UTC)
        session.add_all([
            AuditEvent(event_type="audit.old", metadata_json={}, created_at=now - timedelta(days=366)),
            AuditEvent(event_type="audit.recent", metadata_json={}, created_at=now - timedelta(days=2)),
        ])
        session.commit()

    register_audit_pruning_task(app, factory, RetentionPolicy(audit_event_days=365), interval_seconds=86_400)
    schedule = app.conf.beat_schedule["ape-prune-audit-events"]
    assert schedule == {
        "task": "academic_pe.maintenance.prune_audit_events",
        "schedule": 86_400,
        "options": {"queue": "maintenance", "routing_key": "maintenance"},
    }
    task = app.tasks["academic_pe.maintenance.prune_audit_events"]
    task.apply().get()
    task.apply().get()

    with factory() as session:
        assert [event.event_type for event in session.scalars(select(AuditEvent)).all()] == ["audit.recent"]
