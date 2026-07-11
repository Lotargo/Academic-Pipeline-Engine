from datetime import UTC, datetime

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from academic_pe.auth import AuthSettings, create_auth_router
from academic_pe.persistence.base import Base
from academic_pe.persistence.models import ActorRole, LoginSession, Membership, User, UserStatus


def app_and_sessions():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    router = create_auth_router(sessions, AuthSettings(jwt_secret="x" * 32))
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
