from base64 import urlsafe_b64encode

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from academic_pe.auth import AuthSettings, create_auth_router
from academic_pe.persistence.base import Base
from academic_pe.persistence.models import Credential, UserPreference, WorkspaceMemberSettings
from academic_pe.user_settings import create_user_settings_router


def app_and_sessions(monkeypatch):
    monkeypatch.setenv("APE_CREDENTIAL_MASTER_KEY", urlsafe_b64encode(b"s" * 32).decode().rstrip("="))
    monkeypatch.setenv("APE_CREDENTIAL_WRAPPER", "local-aes")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    auth_router = create_auth_router(sessions, AuthSettings(jwt_secret="x" * 32))
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(create_user_settings_router(sessions, auth_router.principal_dependency))
    return TestClient(app), sessions


def register(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/api/auth/register", json={"email": email, "password": "correct horse battery staple"})
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_personal_settings_and_credentials_are_isolated_by_user_and_workspace(monkeypatch):
    client, sessions = app_and_sessions(monkeypatch)
    alice = register(client, "alice@example.com")
    bob = register(client, "bob@example.com")

    initial = client.get("/api/settings/me", headers=alice)
    assert initial.status_code == 200
    assert initial.json()["profile"] == {"display_name": None, "language": "ru", "theme": "system"}

    updated = client.put("/api/settings/me", headers=alice, json={
        "display_name": "Алиса",
        "language": "en",
        "theme": "dark",
        "editor_defaults": {"academic_mode": True, "web_search_enabled": True, "author": "Alice"},
    })
    assert updated.status_code == 200
    assert updated.json()["profile"] == {"display_name": "Алиса", "language": "en", "theme": "dark"}
    assert updated.json()["editor_defaults"]["academic_mode"] is True

    no_credential = client.put("/api/provider-settings", headers=alice, json={
        "provider_id": "openai", "model_id": "gpt-5.4", "credential_policy": "user_only",
    })
    assert no_credential.status_code == 422

    created = client.post("/api/credentials", headers=alice, json={
        "provider_id": "openai", "label": "Мой ключ", "secret": "super-secret-value",
    })
    assert created.status_code == 201
    credential = created.json()
    assert credential["masked_value"] == "••••••••"
    assert "secret" not in credential

    selection = client.put("/api/provider-settings", headers=alice, json={
        "provider_id": "openai", "model_id": "gpt-5.4", "credential_policy": "user_only",
    })
    assert selection.status_code == 200
    assert selection.json()["credential_policy"] == "user_only"

    bob_snapshot = client.get("/api/provider-settings", headers=bob)
    assert bob_snapshot.status_code == 200
    assert bob_snapshot.json()["credentials"] == []
    assert bob_snapshot.json()["selection"] is None
    assert client.delete(f"/api/credentials/{credential['id']}", headers=bob).status_code == 404

    with sessions() as session:
        assert len(session.scalars(select(UserPreference)).all()) == 1
        assert len(session.scalars(select(WorkspaceMemberSettings)).all()) == 1
        assert len(session.scalars(select(Credential)).all()) == 1
