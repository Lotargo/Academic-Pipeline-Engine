from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from academic_pe.jobs import InvalidJobTransition, JobLifecycleRepository
from academic_pe.persistence.base import Base
from academic_pe.persistence.models import (AttemptStatus, Job, JobAttempt, JobCheckpoint,
    JobEvent, JobStatus, Membership, MembershipRole, Organization, OrganizationKind, User, Workspace)


@pytest.fixture
def context():
    engine = create_engine("sqlite://", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(engine, expire_on_commit=False)()
    user = User(email="user@example.com", password_hash="password-reset-required")
    session.add(user); session.flush()
    organization = Organization(owner_user_id=user.id, kind=OrganizationKind.PERSONAL, name="Personal")
    session.add(organization); session.flush()
    workspace = Workspace(organization_id=organization.id, name="Personal")
    session.add(workspace); session.flush()
    session.add(Membership(workspace_id=workspace.id, user_id=user.id, membership_role=MembershipRole.OWNER))
    job = Job(workspace_id=workspace.id, created_by_user_id=user.id, kind="generation", payload={})
    session.add(job); session.commit()
    yield session, workspace, job
    session.close()


def test_transitions_attempt_stage_checkpoint_and_idempotency(context):
    session, workspace, job = context
    lifecycle = JobLifecycleRepository(session)
    lifecycle.transition(job.id, workspace.id, JobStatus.QUEUED)
    attempt = lifecycle.begin_attempt(job.id, workspace.id, "worker-1")
    lifecycle.heartbeat(job.id, workspace.id, "worker-1")
    stage = lifecycle.update_stage(job.id, workspace.id, "research", 50)
    lifecycle.update_stage(job.id, workspace.id, "research", 20)
    assert stage.progress == 50
    first = lifecycle.save_checkpoint(job.id, workspace.id, "research", {"section": 1})
    second = lifecycle.save_checkpoint(job.id, workspace.id, "research", {"section": 2})
    assert first.id == second.id and second.payload == {"section": 2}
    lifecycle.complete_attempt(job.id, workspace.id, JobStatus.SUCCEEDED)
    lifecycle.complete_attempt(job.id, workspace.id, JobStatus.SUCCEEDED)
    session.commit()
    assert attempt.status == AttemptStatus.SUCCEEDED
    assert job.status == JobStatus.SUCCEEDED
    assert session.scalars(select(JobCheckpoint)).all() == [first]
    with pytest.raises(InvalidJobTransition):
        lifecycle.transition(job.id, workspace.id, JobStatus.RUNNING)


def test_cancellation_is_idempotent_and_tenant_scoped(context):
    session, workspace, job = context
    lifecycle = JobLifecycleRepository(session)
    lifecycle.request_cancellation(job.id, workspace.id)
    requested = job.cancel_requested_at
    lifecycle.request_cancellation(job.id, workspace.id)
    lifecycle.acknowledge_cancellation(job.id, workspace.id)
    lifecycle.acknowledge_cancellation(job.id, workspace.id)
    session.commit()
    assert job.cancel_requested_at == requested
    assert job.status == JobStatus.CANCELLED
    assert session.scalars(select(JobEvent).where(
        JobEvent.event_type == "job.cancellation.requested")).all().__len__() == 1
    with pytest.raises(KeyError):
        lifecycle.request_cancellation(job.id, User().id)


def test_stale_attempt_is_requeued_and_resumes_from_checkpoint(context):
    session, workspace, job = context
    lifecycle = JobLifecycleRepository(session)
    lifecycle.transition(job.id, workspace.id, JobStatus.QUEUED)
    attempt = lifecycle.begin_attempt(job.id, workspace.id, "dead-worker")
    checkpoint = lifecycle.save_checkpoint(job.id, workspace.id, "write", {"completed_sections": [1, 2]})
    job.heartbeat_at = datetime.now(UTC) - timedelta(minutes=10)
    session.commit()
    recovered = lifecycle.recover_interrupted(timedelta(minutes=5))
    session.commit()
    assert recovered == [job.id]
    assert job.status == JobStatus.QUEUED
    assert attempt.status == AttemptStatus.INTERRUPTED
    assert checkpoint.payload["completed_sections"] == [1, 2]
    retry = lifecycle.begin_attempt(job.id, workspace.id, "worker-2")
    assert retry.number == 2
