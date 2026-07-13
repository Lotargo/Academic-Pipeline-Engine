from datetime import UTC, datetime

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from academic_pe.auth import AuthSettings, create_auth_router
from academic_pe.observability import ObservabilityEvent, TelemetryStore
from academic_pe.persistence.base import Base
from academic_pe.persistence.models import (ActorRole, AuditEvent, Job, JobStatus, LoginSession,
    Membership, OutboxEvent, User, UserStatus)
from academic_pe.providers import Capability, InMemoryProviderRegistry, ModelMetadata, ProviderDefinition
from academic_pe.providers.resources import BudgetKind, BudgetState, FairUsePolicy, ResourceCoordinator


def app_and_sessions(provider_registry=None, resource_coordinator=None, health_snapshot=None):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    router = create_auth_router(
        sessions,
        AuthSettings(jwt_secret="x" * 32),
        provider_registry,
        resource_coordinator,
        health_snapshot,
    )
    app = FastAPI()

    @app.get("/admin")
    def admin(_=Depends(router.admin_dependency)):  # type: ignore[attr-defined]
        return {"ok": True}

    @app.get("/workspaces/{workspace_id}")
    def workspace(workspace_id: str, _=Depends(router.workspace_dependency)):  # type: ignore[attr-defined]
        return {"id": workspace_id}

    app.include_router(router)
    return TestClient(app), sessions


def register(client: TestClient, email="user@example.com"):
    return client.post("/api/auth/register", json={"email": email, "password": "correct horse battery staple"})


def test_registration_login_rotation_and_logout():
    client, sessions = app_and_sessions()
    registered = register(client)
    assert registered.status_code == 201
    first = registered.json()
    assert client.post("/api/auth/refresh", json={"refresh_token": first["refresh_token"]}).status_code == 200
    rotated = client.post("/api/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert rotated.status_code == 401

    login = client.post("/api/auth/login", json={"email": "USER@example.com", "password": "correct horse battery staple"})
    assert login.status_code == 200
    refresh = login.json()["refresh_token"]
    assert client.post("/api/auth/logout", json={"refresh_token": refresh}).status_code == 204
    assert client.post("/api/auth/refresh", json={"refresh_token": refresh}).status_code == 401
    with sessions() as session:
        user = session.scalar(select(User))
        assert user.password_hash != "correct horse battery staple"
        assert session.scalar(select(Membership).where(Membership.user_id == user.id)) is not None


def test_user_cannot_escalate_or_cross_tenant_boundary():
    client, sessions = app_and_sessions()
    one = register(client, "one@example.com").json()
    register(client, "two@example.com")
    with sessions() as session:
        users = session.scalars(select(User).order_by(User.email)).all()
        memberships = session.scalars(select(Membership).order_by(Membership.user_id)).all()
        workspace_by_user = {m.user_id: m.workspace_id for m in memberships}
        first = next(u for u in users if u.email == "one@example.com")
        own = workspace_by_user[first.id]
        foreign = next(m.workspace_id for m in memberships if m.user_id != first.id)
    headers = {"Authorization": f"Bearer {one['access_token']}"}
    assert client.get("/admin", headers=headers).status_code == 403
    assert client.get(f"/workspaces/{own}", headers=headers).status_code == 200
    assert client.get(f"/workspaces/{foreign}", headers=headers).status_code == 404
    assert client.get("/api/auth/admin/users", headers=headers).status_code == 403
    assert client.get("/api/auth/admin/audit-events", headers=headers).status_code == 403
    assert client.get("/api/auth/admin/health", headers=headers).status_code == 403


def test_admin_can_view_safe_user_metadata_only():
    client, sessions = app_and_sessions()
    admin_tokens = register(client, "admin@example.com").json()
    register(client, "member@example.com")
    with sessions() as session:
        admin = session.scalar(select(User).where(User.email == "admin@example.com"))
        admin.actor_role = ActorRole.ADMIN
        session.commit()
    headers = {"Authorization": f"Bearer {admin_tokens['access_token']}"}
    response = client.get("/api/auth/admin/users", headers=headers)
    assert response.status_code == 200
    users = response.json()
    assert {user["email"] for user in users} == {"admin@example.com", "member@example.com"}
    assert all("password_hash" not in user and "token_version" not in user for user in users)


def test_admin_resource_snapshot_hides_credentials_and_unknown_quota_balance():
    registry = InMemoryProviderRegistry()
    registry.register(ProviderDefinition("openai", (ModelMetadata("gpt-test", frozenset({Capability.TEXT_GENERATION})),), display_name="OpenAI"))
    resources = ResourceCoordinator(FairUsePolicy(2, 4))
    resources.set_budget("openai", BudgetState(BudgetKind.UNKNOWN))
    client, sessions = app_and_sessions(registry, resources)
    tokens = register(client, "admin@example.com").json()
    with sessions() as session:
        session.scalar(select(User)).actor_role = ActorRole.ADMIN
        session.commit()
    response = client.get("/api/auth/admin/resources", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert response.status_code == 200
    body = response.json()
    assert body["providers"][0]["models"] == [{"id": "gpt-test", "capabilities": ["text_generation"]}]
    assert body["providers"][0]["budget"] == {"kind": "unknown"}
    assert body["providers"][0]["platform_credential"] is None
    assert body["fair_use"] == {"max_active_per_user": 2, "max_queued_per_user": 4}


def test_admin_jobs_snapshot_exposes_only_aggregate_lifecycle_and_outbox_counts():
    client, sessions = app_and_sessions()
    tokens = register(client, "admin@example.com").json()
    with sessions() as session:
        admin = session.scalar(select(User))
        admin.actor_role = ActorRole.ADMIN
        workspace = session.scalar(select(Membership).where(Membership.user_id == admin.id)).workspace_id
        job = Job(workspace_id=workspace, created_by_user_id=admin.id, kind="pipeline", status=JobStatus.QUEUED,
                  payload={"topic": "must not be exposed"})
        session.add(job)
        session.flush()
        session.add(OutboxEvent(job_id=job.id, workload="generation", attempts=1, available_at=datetime.now(UTC)))
        session.commit()
    response = client.get("/api/auth/admin/jobs", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert response.status_code == 200
    body = response.json()
    assert {item["status"]: item["count"] for item in body["jobs"]}["queued"] == 1
    assert body["queues"] == [{"workload": "generation", "pending": 1, "retrying": 1}]
    assert "must not be exposed" not in str(body)


def test_context_only_exposes_callers_active_workspace_memberships():
    client, _ = app_and_sessions()
    one = register(client, "one@example.com").json()
    register(client, "two@example.com")
    context = client.get("/api/auth/context", headers={"Authorization": f"Bearer {one['access_token']}"})
    assert context.status_code == 200
    body = context.json()
    assert body["email"] == "one@example.com"
    assert body["role"] == "user"
    assert len(body["workspaces"]) == 1
    assert body["workspaces"][0]["name"] == "Personal"


def test_admin_audit_and_health_views_are_protected_redacted_and_audited():
    telemetry = TelemetryStore()
    telemetry.record(ObservabilityEvent(
        event_type="worker.delivery.failed",
        severity="error",
        correlation_id="trace_12345678",
        source="queue_worker",
        outcome="failure",
        details={"credential": "must-not-leak"},
    ))
    client, sessions = app_and_sessions(health_snapshot=telemetry.admin_snapshot)
    tokens = register(client, "admin@example.com").json()
    with sessions() as session:
        admin = session.scalar(select(User))
        admin.actor_role = ActorRole.ADMIN
        session.add(AuditEvent(
            event_type="credential.replaced",
            actor_user_id=admin.id,
            metadata_json={"correlation_id": "trace_12345678", "credential": "must-not-leak"},
        ))
        session.commit()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    audit_response = client.get("/api/auth/admin/audit-events", headers=headers)
    assert audit_response.status_code == 200
    audit_body = audit_response.json()
    assert audit_body["events"][0]["event_type"] == "credential.replaced"
    assert audit_body["events"][0]["correlation_id"] == "trace_12345678"
    assert "metadata_json" not in str(audit_body)
    assert "must-not-leak" not in str(audit_body)

    health_response = client.get("/api/auth/admin/health", headers=headers)
    assert health_response.status_code == 200
    health_body = health_response.json()
    assert health_body["status"] == "ok"
    assert health_body["telemetry"]["event_counts"] == [{
        "event_type": "worker.delivery.failed",
        "severity": "error",
        "outcome": "failure",
        "count": 1,
    }]
    assert "must-not-leak" not in str(health_body)

    with sessions() as session:
        assert set(session.scalars(select(AuditEvent.event_type)).all()) >= {
            "credential.replaced", "admin.audit.viewed", "admin.health.viewed",
        }


def test_block_and_token_version_revoke_access():
    client, sessions = app_and_sessions()
    tokens = register(client).json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    with sessions() as session:
        user = session.scalar(select(User))
        user.token_version += 1
        session.commit()
    assert client.get("/admin", headers=headers).status_code == 401
    with sessions() as session:
        user = session.scalar(select(User))
        user.status = UserStatus.BLOCKED
        session.commit()
    assert client.post("/api/auth/login", json={"email": "user@example.com", "password": "correct horse battery staple"}).status_code == 403
