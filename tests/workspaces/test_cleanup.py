from datetime import UTC, datetime
from io import BytesIO

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from academic_pe.auth import AuthSettings, create_auth_router
from academic_pe.persistence.base import Base
from academic_pe.persistence.models import (
    Artifact, AuditEvent, Job, JobStatus, Membership, OutboxEvent, UsageEvent,
    User, WorkspaceCleanupRequest, WorkspaceCleanupStatus,
)
from academic_pe.storage import LocalArtifactStorage
from academic_pe.workspaces import create_workspace_cleanup_router


def app_and_sessions(tmp_path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    auth_router = create_auth_router(sessions, AuthSettings(jwt_secret="x" * 32))
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(create_workspace_cleanup_router(
        sessions, auth_router.principal_dependency, LocalArtifactStorage(tmp_path, b"test-secret"),
    ))
    return TestClient(app), sessions


def register(client, email):
    response = client.post("/api/auth/register", json={"email": email, "password": "correct horse battery staple"})
    assert response.status_code == 201
    return response.json()


def workspace_for(sessions, email):
    with sessions() as session:
        user = session.scalar(select(User).where(User.email == email))
        return user, session.scalar(select(Membership).where(Membership.user_id == user.id)).workspace_id


def test_owner_cleanup_is_scoped_audited_and_idempotent(tmp_path):
    client, sessions = app_and_sessions(tmp_path)
    tokens = register(client, "owner@example.com")
    register(client, "other@example.com")
    owner, workspace = workspace_for(sessions, "owner@example.com")
    other, other_workspace = workspace_for(sessions, "other@example.com")
    storage = LocalArtifactStorage(tmp_path, b"test-secret")
    owned = storage.upload(workspace, "paper.pdf", BytesIO(b"owned"))
    foreign = storage.upload(other_workspace, "paper.pdf", BytesIO(b"foreign"))
    with sessions() as session:
        job = Job(workspace_id=workspace, created_by_user_id=owner.id, kind="pipeline", status=JobStatus.SUCCEEDED, payload={})
        other_job = Job(workspace_id=other_workspace, created_by_user_id=other.id, kind="pipeline", status=JobStatus.SUCCEEDED, payload={})
        session.add_all([job, other_job]); session.flush()
        session.add_all([
            Artifact(workspace_id=workspace, job_id=job.id, created_by_user_id=owner.id, storage_key=owned.storage_key, artifact_type="document", filename="paper.pdf"),
            Artifact(workspace_id=other_workspace, job_id=other_job.id, created_by_user_id=other.id, storage_key=foreign.storage_key, artifact_type="document", filename="paper.pdf"),
            OutboxEvent(job_id=job.id, workload="pipeline", available_at=datetime.now(UTC)),
            UsageEvent(workspace_id=workspace, actor_user_id=owner.id, job_id=job.id, provider="test", metric="tokens", quantity=1),
        ])
        session.commit()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    denied = client.post(f"/api/workspaces/{other_workspace}/cleanup-requests", headers=headers,
                         json={"confirmation": "DELETE MY WORKSPACE DATA"})
    assert denied.status_code == 404
    requested = client.post(f"/api/workspaces/{workspace}/cleanup-requests", headers=headers,
                            json={"confirmation": "DELETE MY WORKSPACE DATA"})
    assert requested.status_code == 201
    body = requested.json()
    assert body["confirmation_token"] not in str(body["id"])
    completed = client.post(f"/api/workspaces/{workspace}/cleanup-requests/{body['id']}/confirm", headers=headers,
                            json={"confirmation_token": body["confirmation_token"]})
    assert completed.json()["status"] == "completed"
    repeated = client.post(f"/api/workspaces/{workspace}/cleanup-requests/{body['id']}/confirm", headers=headers,
                           json={"confirmation_token": body["confirmation_token"]})
    assert repeated.json() == completed.json()
    with sessions() as session:
        assert session.scalar(select(Job).where(Job.workspace_id == workspace)) is None
        assert session.scalar(select(Artifact).where(Artifact.workspace_id == workspace)) is None
        assert session.scalar(select(Job).where(Job.workspace_id == other_workspace)) is not None
        assert session.scalar(select(Artifact).where(Artifact.workspace_id == other_workspace)) is not None
        usage = session.scalar(select(UsageEvent).where(UsageEvent.workspace_id == workspace))
        assert usage is not None and usage.job_id is None
        cleanup = session.scalar(select(WorkspaceCleanupRequest))
        assert cleanup.status == WorkspaceCleanupStatus.COMPLETED
        assert cleanup.confirmation_token_hash != body["confirmation_token"]
        assert {"workspace.cleanup.requested", "workspace.cleanup.completed"}.issubset(
            set(session.scalars(select(AuditEvent.event_type)).all())
        )
    assert storage.download(other_workspace, foreign.storage_key) == b"foreign"
    try:
        storage.download(workspace, owned.storage_key)
        assert False, "owned storage object must be deleted"
    except FileNotFoundError:
        pass


def test_confirmation_requires_exact_token_and_explicit_phrase(tmp_path):
    client, sessions = app_and_sessions(tmp_path)
    tokens = register(client, "owner@example.com")
    _, workspace = workspace_for(sessions, "owner@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert client.post(f"/api/workspaces/{workspace}/cleanup-requests", headers=headers,
                       json={"confirmation": "yes"}).status_code == 422
    requested = client.post(f"/api/workspaces/{workspace}/cleanup-requests", headers=headers,
                            json={"confirmation": "DELETE MY WORKSPACE DATA"}).json()
    response = client.post(f"/api/workspaces/{workspace}/cleanup-requests/{requested['id']}/confirm", headers=headers,
                           json={"confirmation_token": "x" * 32})
    assert response.status_code == 400
