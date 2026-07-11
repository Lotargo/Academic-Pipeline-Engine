from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from academic_pe.auth import AuthSettings, create_auth_router
from academic_pe.jobs import create_jobs_router
from academic_pe.persistence.base import Base


def job_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    auth = create_auth_router(sessions, AuthSettings(jwt_secret="x" * 32))
    app = FastAPI()
    app.include_router(auth)
    app.include_router(create_jobs_router(sessions, auth.principal_dependency))  # type: ignore[attr-defined]
    return TestClient(app)


def register(client: TestClient, email: str) -> dict:
    response = client.post("/api/auth/register", json={"email": email, "password": "correct horse battery staple"})
    assert response.status_code == 201
    return response.json()


def test_job_api_creates_lists_cancels_and_hides_foreign_jobs():
    client = job_client()
    one = register(client, "one@example.com")
    two = register(client, "two@example.com")
    one_headers = {"Authorization": f"Bearer {one['access_token']}"}
    two_headers = {"Authorization": f"Bearer {two['access_token']}"}

    created = client.post("/api/jobs", headers=one_headers, json={"kind": "pipeline", "topic": "Tenant-safe topic"})
    assert created.status_code == 201
    job = created.json()
    assert job["status"] == "pending"
    assert job["topic"] == "Tenant-safe topic"

    listed = client.get("/api/jobs?active=true", headers=one_headers)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["jobs"]] == [job["id"]]
    assert client.get(f"/api/jobs/{job['id']}", headers=two_headers).status_code == 404

    cancelled = client.post(f"/api/jobs/{job['id']}/cancel", headers=one_headers)
    assert cancelled.status_code == 202
    assert cancelled.json()["cancel_requested_at"] is not None
    assert client.post(f"/api/jobs/{job['id']}/cancel", headers=one_headers).status_code == 202
