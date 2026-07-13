import logging
from uuid import uuid4

import pytest
from cryptography.exceptions import InvalidTag
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from academic_pe.persistence.base import Base
from academic_pe.persistence.models import (AuditEvent, Credential, CredentialStatus, Membership,
    MembershipRole, Organization, OrganizationKind, User, Workspace)
from academic_pe.secrets.crypto import LocalAesKeyWrapper
from academic_pe.secrets.redaction import REDACTED, SecretRedactionFilter, redact
from academic_pe.secrets.store import CredentialAccessDenied, SqlAlchemyCredentialStore, WorkerPurpose


@pytest.fixture
def context():
    engine = create_engine("sqlite://", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    session = factory()
    user = User(email="user@example.com", password_hash="password-reset-required")
    session.add(user); session.flush()
    organization = Organization(owner_user_id=user.id, kind=OrganizationKind.PERSONAL, name="Personal")
    session.add(organization); session.flush()
    workspace = Workspace(organization_id=organization.id, name="Personal")
    session.add(workspace); session.flush()
    session.add(Membership(workspace_id=workspace.id, user_id=user.id, membership_role=MembershipRole.OWNER))
    session.commit()
    yield session, user, workspace
    session.close()


def test_create_replace_delete_and_database_dump_is_opaque(context):
    session, user, workspace = context
    wrapper = LocalAesKeyWrapper(b"a" * 32, "kms/key/1")
    store = SqlAlchemyCredentialStore(session, wrapper)
    credential = store.create(workspace.id, user.id, "openai", "primary", "sk-plaintext-secret")
    assert b"sk-plaintext-secret" not in credential.encrypted_payload
    assert "sk-plaintext-secret" not in repr(credential.__dict__)
    assert store.use(credential.id, workspace.id, WorkerPurpose.GENERATION) == "sk-plaintext-secret"
    store.replace(credential.id, workspace.id, "replacement-secret")
    assert credential.encryption_version == 2
    assert store.use(credential.id, workspace.id, WorkerPurpose.OCR) == "replacement-secret"
    store.delete(credential.id, workspace.id, user.id)
    assert credential.status == CredentialStatus.DELETED
    events = session.scalars(select(AuditEvent).order_by(AuditEvent.created_at)).all()
    assert events and all(event.metadata_json["correlation_id"] == "service_00000000" for event in events)
    with pytest.raises(KeyError):
        store.use(credential.id, workspace.id, WorkerPurpose.GENERATION)


def test_worker_permissions_tenant_boundary_rotation_and_tamper(context):
    session, user, workspace = context
    old = LocalAesKeyWrapper(b"a" * 32, "kms/key/1")
    store = SqlAlchemyCredentialStore(session, old)
    credential = store.create(workspace.id, user.id, "anthropic", "primary", "valuable-secret")
    for purpose in (WorkerPurpose.API, WorkerPurpose.ADMIN):
        with pytest.raises(CredentialAccessDenied):
            store.use(credential.id, workspace.id, purpose)
    with pytest.raises(KeyError):
        store.use(credential.id, uuid4(), WorkerPurpose.GENERATION)
    new = LocalAesKeyWrapper(b"b" * 32, "kms/key/2")
    store.rewrap(credential.id, workspace.id, new)
    assert credential.encryption_key_id == "kms/key/2"
    assert store.use(credential.id, workspace.id, WorkerPurpose.GENERATION) == "valuable-secret"
    credential.encrypted_payload = bytes([credential.encrypted_payload[0] ^ 1]) + credential.encrypted_payload[1:]
    session.commit()
    with pytest.raises(InvalidTag):
        store.use(credential.id, workspace.id, WorkerPurpose.GENERATION)


def test_redaction_covers_structured_values_and_bearer_tokens():
    value = redact({"api_key": "secret", "nested": {"password": "pw"},
                    "message": "Authorization: Bearer abc.def.ghi"})
    assert value["api_key"] == REDACTED
    assert value["nested"]["password"] == REDACTED
    assert "abc.def.ghi" not in value["message"]
    assert "raw-value" not in redact("api_key=raw-value")
    record = logging.LogRecord("test", logging.INFO, __file__, 1,
                               "request %s", ({"token": "plaintext"},), None)
    SecretRedactionFilter().filter(record)
    assert "plaintext" not in record.getMessage()
