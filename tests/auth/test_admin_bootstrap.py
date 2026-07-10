from datetime import timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from academic_pe.admin_bootstrap import (BootstrapError, activate_admin_invite,
    bootstrap_first_admin, create_admin_invite)
from academic_pe.auth.security import hash_refresh_token
from academic_pe.persistence.base import Base
from academic_pe.persistence.models import ActorRole, AdminInvite, AuditEvent, User


@pytest.fixture
def sessions():
    engine = create_engine("sqlite://", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


def test_first_admin_is_reproducible_and_exclusive(sessions):
    with sessions() as session:
        first = bootstrap_first_admin(session, "ROOT@example.com", "correct horse battery staple")
        same = bootstrap_first_admin(session, "root@example.com", "ignored password value")
        assert same.id == first.id
        assert first.actor_role == ActorRole.ADMIN
        with pytest.raises(BootstrapError, match="already exists"):
            bootstrap_first_admin(session, "other@example.com", "correct horse battery staple")
        assert session.scalar(select(AuditEvent).where(
            AuditEvent.event_type == "admin.bootstrap.created")) is not None


def test_invite_hash_single_use_expiry_and_audit(sessions):
    with sessions() as session:
        admin = bootstrap_first_admin(session, "admin@example.com", "correct horse battery staple")
        user = User(email="user@example.com", password_hash="password-reset-required")
        session.add(user)
        session.commit()
        invite, raw = create_admin_invite(session, admin.id)
        assert invite.token_hash == hash_refresh_token(raw)
        assert raw != invite.token_hash
        promoted = activate_admin_invite(session, user.id, raw)
        assert promoted.actor_role == ActorRole.ADMIN
        assert promoted.token_version == 1
        with pytest.raises(BootstrapError, match="already_used"):
            activate_admin_invite(session, user.id, raw)
        events = session.scalars(select(AuditEvent.event_type)).all()
        assert "admin.invite.created" in events
        assert "admin.invite.activated" in events
        assert "admin.invite.rejected" in events


def test_expired_invite_and_non_admin_issuance_are_rejected(sessions):
    with sessions() as session:
        admin = bootstrap_first_admin(session, "admin@example.com", "correct horse battery staple")
        user = User(email="user@example.com", password_hash="password-reset-required")
        session.add(user)
        session.commit()
        with pytest.raises(BootstrapError, match="active administrator"):
            create_admin_invite(session, user.id)
        invite, raw = create_admin_invite(session, admin.id, timedelta(microseconds=1))
        with pytest.raises(BootstrapError, match="expired"):
            activate_admin_invite(session, user.id, raw)
        session.refresh(invite)
        assert invite.used_at is None
