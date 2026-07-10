from __future__ import annotations

import argparse
import getpass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from academic_pe.auth.security import hash_password, hash_refresh_token, new_refresh_token
from academic_pe.persistence.config import DatabaseSettings, create_worker_engine, create_worker_session_factory
from academic_pe.persistence.models import (ActorRole, AdminInvite, AuditEvent, Membership,
    MembershipRole, Organization, OrganizationKind, User, UserStatus, Workspace)


class BootstrapError(ValueError):
    pass


def _audit(session: Session, event: str, actor: UUID | None = None,
           target: UUID | None = None, **metadata: object) -> None:
    session.add(AuditEvent(event_type=event, actor_user_id=actor,
                           target_user_id=target, metadata_json=metadata))


def bootstrap_first_admin(session: Session, email: str, password: str) -> User:
    email = email.strip().lower()
    existing_admin = session.scalar(select(User).where(User.actor_role == ActorRole.ADMIN))
    user = session.scalar(select(User).where(User.email == email))
    if existing_admin is not None:
        if user is not None and existing_admin.id == user.id:
            return user
        raise BootstrapError("an administrator already exists")
    if user is None:
        user = User(email=email, password_hash=hash_password(password), actor_role=ActorRole.ADMIN)
        session.add(user)
        session.flush()
        organization = Organization(owner_user_id=user.id, kind=OrganizationKind.PERSONAL, name="Personal")
        session.add(organization)
        session.flush()
        workspace = Workspace(organization_id=organization.id, name="Personal")
        session.add(workspace)
        session.flush()
        session.add(Membership(workspace_id=workspace.id, user_id=user.id,
                               membership_role=MembershipRole.OWNER))
    else:
        if user.status != UserStatus.ACTIVE:
            raise BootstrapError("target user is not active")
        user.actor_role = ActorRole.ADMIN
        user.token_version += 1
    _audit(session, "admin.bootstrap.created", target=user.id, email=email)
    session.commit()
    return user


def create_admin_invite(session: Session, creator_id: UUID,
                        ttl: timedelta = timedelta(hours=24)) -> tuple[AdminInvite, str]:
    creator = session.get(User, creator_id)
    if creator is None or creator.status != UserStatus.ACTIVE or creator.actor_role != ActorRole.ADMIN:
        raise BootstrapError("active administrator required")
    if ttl <= timedelta(0):
        raise BootstrapError("invite ttl must be positive")
    raw = new_refresh_token()
    invite = AdminInvite(token_hash=hash_refresh_token(raw), created_by_user_id=creator.id,
                          expires_at=datetime.now(UTC) + ttl)
    session.add(invite)
    session.flush()
    _audit(session, "admin.invite.created", actor=creator.id, invite_id=str(invite.id),
           expires_at=invite.expires_at.isoformat())
    session.commit()
    return invite, raw


def activate_admin_invite(session: Session, user_id: UUID, raw_token: str) -> User:
    now = datetime.now(UTC)
    invite = session.scalar(select(AdminInvite).where(
        AdminInvite.token_hash == hash_refresh_token(raw_token)).with_for_update())
    user = session.get(User, user_id)
    reason = None
    if user is None or user.status != UserStatus.ACTIVE:
        reason = "inactive_user"
    elif invite is None:
        reason = "invalid_token"
    elif invite.used_at is not None:
        reason = "already_used"
    elif invite.expires_at.replace(tzinfo=UTC) <= now:
        reason = "expired"
    if reason:
        _audit(session, "admin.invite.rejected", target=user_id, reason=reason)
        session.commit()
        raise BootstrapError(reason)
    invite.used_at = now
    invite.used_by_user_id = user.id
    user.actor_role = ActorRole.ADMIN
    user.token_version += 1
    _audit(session, "admin.invite.activated", actor=user.id, target=user.id,
           invite_id=str(invite.id))
    session.commit()
    return user


def main() -> int:
    parser = argparse.ArgumentParser(description="One-off APE administrator bootstrap")
    sub = parser.add_subparsers(dest="command", required=True)
    first = sub.add_parser("first-admin")
    first.add_argument("--email", required=True)
    first.add_argument("--password", help="omit to read securely from the terminal")
    invite = sub.add_parser("create-invite")
    invite.add_argument("--creator-id", type=UUID, required=True)
    invite.add_argument("--ttl-hours", type=int, default=24)
    args = parser.parse_args()
    factory = create_worker_session_factory(create_worker_engine(DatabaseSettings.from_env()))
    with factory() as session:
        if args.command == "first-admin":
            password = args.password or getpass.getpass("Initial administrator password: ")
            user = bootstrap_first_admin(session, args.email, password)
            print(f"administrator ready: {user.id}")
        else:
            _, raw = create_admin_invite(session, args.creator_id, timedelta(hours=args.ttl_hours))
            print(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
