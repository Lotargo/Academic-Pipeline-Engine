from datetime import UTC, datetime, timedelta
import json
from uuid import UUID, uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from academic_pe.auth import (
    ExternalIdentityClaims,
    IdentityVerificationError,
    MockExternalIdentityVerifier,
    SupabaseIdentitySettings,
    SupabaseJwtVerifier,
    create_auth_router,
)
from academic_pe.persistence.base import Base
from academic_pe.persistence.models import ActorRole, ExternalIdentity, Membership, User


class TokenMapVerifier:
    def __init__(self, values: dict[str, ExternalIdentityClaims]):
        self.values = values

    def verify(self, bearer_token: str) -> ExternalIdentityClaims:
        try:
            return self.values[bearer_token]
        except KeyError as exc:
            raise IdentityVerificationError("unknown mock token") from exc


def external_client(verifier=None):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    router = create_auth_router(sessions, identity_verifier=verifier or MockExternalIdentityVerifier())
    app = FastAPI()

    @app.get("/admin")
    def admin(_=Depends(router.admin_dependency)):  # type: ignore[attr-defined]
        return {"ok": True}

    @app.get("/workspaces/{workspace_id}")
    def workspace(workspace_id: str, _=Depends(router.workspace_dependency)):  # type: ignore[attr-defined]
        return {"id": workspace_id}

    app.include_router(router)
    return TestClient(app), sessions


def test_mock_external_identity_provisions_once_and_service_router_has_no_password_endpoints():
    client, sessions = external_client()
    headers = {"Authorization": "Bearer mock:google"}
    first = client.get("/api/auth/context", headers=headers)
    second = client.get("/api/auth/context", headers=headers)

    assert first.status_code == second.status_code == 200
    assert first.json()["user_id"] == second.json()["user_id"]
    assert first.json()["email"] == "mock-google@example.invalid"
    assert len(first.json()["workspaces"]) == 1
    assert client.post("/api/auth/login", json={}).status_code == 404
    assert client.post("/api/auth/register", json={}).status_code == 404
    assert client.post("/api/auth/refresh", json={}).status_code == 404
    with sessions() as session:
        assert len(session.scalars(select(User)).all()) == 1
        assert len(session.scalars(select(ExternalIdentity)).all()) == 1
        assert len(session.scalars(select(Membership)).all()) == 1


def test_mock_email_identity_provisions_a_repeatable_service_dev_workspace():
    client, sessions = external_client()
    headers = {"Authorization": "Bearer mock:email:researcher@example.org"}
    first = client.get("/api/auth/context", headers=headers)
    second = client.get("/api/auth/context", headers=headers)

    assert first.status_code == second.status_code == 200
    assert first.json()["user_id"] == second.json()["user_id"]
    assert first.json()["email"] == "researcher@example.org"
    assert len(first.json()["workspaces"]) == 1
    with sessions() as session:
        identity = session.scalar(select(ExternalIdentity))
        assert identity is not None
        assert identity.provider == "email"


def test_external_identity_rejects_invalid_tokens_and_preserves_rbac_and_tenant_boundary():
    first_subject, second_subject = str(uuid4()), str(uuid4())
    verifier = TokenMapVerifier({
        "one": ExternalIdentityClaims("https://project.supabase.test/auth/v1", "google", first_subject, "one@example.test"),
        "two": ExternalIdentityClaims("https://project.supabase.test/auth/v1", "yandex", second_subject, "two@example.test"),
    })
    client, sessions = external_client(verifier)
    assert client.get("/api/auth/context", headers={"Authorization": "Bearer invalid"}).status_code == 401
    one = client.get("/api/auth/context", headers={"Authorization": "Bearer one"}).json()
    two = client.get("/api/auth/context", headers={"Authorization": "Bearer two"}).json()
    assert client.get("/admin", headers={"Authorization": "Bearer one"}).status_code == 403
    assert client.get(f"/workspaces/{one['workspaces'][0]['id']}", headers={"Authorization": "Bearer one"}).status_code == 200
    assert client.get(f"/workspaces/{two['workspaces'][0]['id']}", headers={"Authorization": "Bearer one"}).status_code == 404

    with sessions() as session:
        user = session.get(User, UUID(one["user_id"]))
        assert user is not None
        user.actor_role = ActorRole.ADMIN
        session.commit()
    assert client.get("/admin", headers={"Authorization": "Bearer one"}).status_code == 200


def test_external_identity_never_links_a_legacy_user_by_email():
    subject = str(uuid4())
    verifier = TokenMapVerifier({
        "external": ExternalIdentityClaims("https://project.supabase.test/auth/v1", "google", subject, "shared@example.test"),
    })
    client, sessions = external_client(verifier)
    with sessions() as session:
        session.add(User(email="shared@example.test", password_hash="legacy"))
        session.commit()
    response = client.get("/api/auth/context", headers={"Authorization": "Bearer external"})
    assert response.status_code == 409
    with sessions() as session:
        assert len(session.scalars(select(User)).all()) == 1
        assert session.scalar(select(ExternalIdentity)) is None


def _key_and_jwks(kid: str = "primary"):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk["kid"] = kid
    jwk["use"] = "sig"
    return private_key, {"keys": [jwk]}


def _supabase_token(private_key, *, issuer="https://project.supabase.test/auth/v1", audience="authenticated",
                    expires_at=None, kid="primary"):
    now = datetime.now(UTC)
    return jwt.encode({
        "sub": str(uuid4()),
        "iss": issuer,
        "aud": audience,
        "exp": expires_at or now + timedelta(minutes=5),
        "iat": now,
        "role": "authenticated",
        "email": "person@example.com",
        "app_metadata": {"provider": "google"},
    }, private_key, algorithm="RS256", headers={"kid": kid})


def test_supabase_jwt_verifier_checks_signature_issuer_audience_expiry_and_key_rotation():
    private_key, first_jwks = _key_and_jwks("old")
    next_private_key, next_jwks = _key_and_jwks("new")
    jwks = first_jwks
    calls = []

    def fetcher(_url):
        calls.append(_url)
        return jwks

    settings = SupabaseIdentitySettings(
        issuer="https://project.supabase.test/auth/v1",
        jwks_url="https://project.supabase.test/auth/v1/.well-known/jwks.json",
        jwks_ttl=timedelta(hours=1),
    )
    verifier = SupabaseJwtVerifier(settings, jwks_fetcher=fetcher)
    token = _supabase_token(private_key, kid="old")
    assert verifier.verify(token).provider == "google"

    with pytest.raises(IdentityVerificationError):
        verifier.verify(_supabase_token(next_private_key, kid="old"))
    with pytest.raises(IdentityVerificationError):
        verifier.verify(_supabase_token(private_key, issuer="https://wrong.example/auth/v1", kid="old"))
    with pytest.raises(IdentityVerificationError):
        verifier.verify(_supabase_token(private_key, audience="wrong", kid="old"))
    with pytest.raises(IdentityVerificationError):
        verifier.verify(_supabase_token(private_key, expires_at=datetime.now(UTC) - timedelta(seconds=1), kid="old"))

    jwks = next_jwks
    assert verifier.verify(_supabase_token(next_private_key, kid="new")).email == "person@example.com"
    assert len(calls) == 2  # initial load and one bounded refresh for an unknown key.
