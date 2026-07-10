from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from academic_pe.persistence.base import Base
from academic_pe.persistence.models import (
    ActorRole,
    Artifact,
    Job,
    Membership,
    MembershipRole,
    Organization,
    OrganizationKind,
    User,
    Workspace,
)
from academic_pe.persistence.repositories import SqlAlchemyTenantRepository
from academic_pe.persistence.uow import SqlAlchemyUnitOfWork


@pytest.fixture(params=["sqlite", "postgresql"])
def session_factory(tmp_path, request):
    if request.param == "postgresql":
        database_url = os.getenv("APE_TEST_POSTGRES_URL")
        if not database_url:
            pytest.skip("APE_TEST_POSTGRES_URL is not configured")
    else:
        database_url = f"sqlite:///{tmp_path / 'persistence.sqlite3'}"

    engine = create_engine(database_url)

    if request.param == "sqlite":
        @event.listens_for(engine, "connect")
        def enable_foreign_keys(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False, autoflush=False)
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


def create_workspace(session, email: str) -> tuple[User, Workspace]:
    user = User(id=uuid4(), email=email, actor_role=ActorRole.USER)
    session.add(user)
    session.flush()
    organization = Organization(
        id=uuid4(),
        owner_user_id=user.id,
        kind=OrganizationKind.PERSONAL,
        name=email,
    )
    session.add(organization)
    session.flush()
    workspace = Workspace(id=uuid4(), organization_id=organization.id, name="Personal")
    session.add(workspace)
    session.flush()
    membership = Membership(
        workspace_id=workspace.id,
        user_id=user.id,
        membership_role=MembershipRole.OWNER,
    )
    session.add(membership)
    session.flush()
    return user, workspace


def test_tenant_repository_never_returns_another_workspace(session_factory):
    with session_factory.begin() as session:
        user_a, workspace_a = create_workspace(session, "a@example.test")
        user_b, workspace_b = create_workspace(session, "b@example.test")
        job_a = Job(
            workspace_id=workspace_a.id,
            created_by_user_id=user_a.id,
            kind="generation",
        )
        job_b = Job(
            workspace_id=workspace_b.id,
            created_by_user_id=user_b.id,
            kind="generation",
        )
        session.add_all([job_a, job_b])

    with session_factory() as session:
        repository = SqlAlchemyTenantRepository(session, Job)
        assert repository.get_for_workspace(workspace_a.id, job_b.id) is None
        assert [job.id for job in repository.list_for_workspace(workspace_a.id)] == [
            job_a.id
        ]


def test_unit_of_work_rolls_back_exception(session_factory):
    user_id = uuid4()
    with pytest.raises(RuntimeError):
        with SqlAlchemyUnitOfWork(session_factory) as uow:
            uow.session.add(
                User(id=user_id, email="rollback@example.test", actor_role=ActorRole.USER)
            )
            uow.session.flush()
            raise RuntimeError("force rollback")

    with session_factory() as session:
        assert session.get(User, user_id) is None


def test_artifact_cannot_reference_job_from_another_workspace(session_factory):
    with pytest.raises(IntegrityError):
        with session_factory.begin() as session:
            user_a, workspace_a = create_workspace(session, "owner-a@example.test")
            _user_b, workspace_b = create_workspace(session, "owner-b@example.test")
            job = Job(
                workspace_id=workspace_a.id,
                created_by_user_id=user_a.id,
                kind="generation",
            )
            session.add(job)
            session.flush()
            session.add(
                Artifact(
                    workspace_id=workspace_b.id,
                    job_id=job.id,
                    storage_key=f"{workspace_b.id}/artifact",
                    artifact_type="docx",
                    filename="paper.docx",
                )
            )
