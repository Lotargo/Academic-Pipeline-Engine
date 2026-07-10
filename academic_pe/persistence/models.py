from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from academic_pe.persistence.base import Base


class ActorRole(str, Enum):
    USER = "user"
    ADMIN = "admin"
    SERVICE = "service"


class UserStatus(str, Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    DELETED = "deleted"


class OrganizationKind(str, Enum):
    PERSONAL = "personal"
    TEAM = "team"


class TenantStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETING = "deleting"
    DELETED = "deleted"


class MembershipRole(str, Enum):
    OWNER = "owner"
    MEMBER = "member"


class MembershipStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REMOVED = "removed"


class JobStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CredentialStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    DELETED = "deleted"


def enum_type(enum: type[Enum], name: str) -> SqlEnum:
    return SqlEnum(
        enum,
        name=name,
        native_enum=False,
        values_callable=lambda values: [item.value for item in values],
        validate_strings=True,
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(
        String(512), default="password-reset-required", nullable=False
    )
    token_version: Mapped[int] = mapped_column(default=0, nullable=False)
    actor_role: Mapped[ActorRole] = mapped_column(
        enum_type(ActorRole, "actor_role"), default=ActorRole.USER, nullable=False
    )
    status: Mapped[UserStatus] = mapped_column(
        enum_type(UserStatus, "user_status"), default=UserStatus.ACTIVE, nullable=False
    )


class LoginSession(TimestampMixin, Base):
    __tablename__ = "sessions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    kind: Mapped[OrganizationKind] = mapped_column(
        enum_type(OrganizationKind, "organization_kind"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[TenantStatus] = mapped_column(
        enum_type(TenantStatus, "organization_status"),
        default=TenantStatus.ACTIVE,
        nullable=False,
    )


class Workspace(TimestampMixin, Base):
    __tablename__ = "workspaces"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[TenantStatus] = mapped_column(
        enum_type(TenantStatus, "workspace_status"),
        default=TenantStatus.ACTIVE,
        nullable=False,
    )


class Membership(TimestampMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_memberships_workspace_user"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    membership_role: Mapped[MembershipRole] = mapped_column(
        enum_type(MembershipRole, "membership_role"), nullable=False
    )
    status: Mapped[MembershipStatus] = mapped_column(
        enum_type(MembershipStatus, "membership_status"),
        default=MembershipStatus.ACTIVE,
        nullable=False,
    )


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_jobs_id_workspace"),
        Index("ix_jobs_workspace_created", "workspace_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        enum_type(JobStatus, "job_status"), default=JobStatus.PENDING, nullable=False
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(120))
    error_message: Mapped[str | None] = mapped_column(Text)


class Artifact(TimestampMixin, Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_id", "workspace_id"],
            ["jobs.id", "jobs.workspace_id"],
            name="fk_artifacts_job_workspace",
            ondelete="RESTRICT",
        ),
        Index("ix_artifacts_workspace_created", "workspace_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    job_id: Mapped[UUID | None] = mapped_column(Uuid)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    storage_key: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(80), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    media_type: Mapped[str | None] = mapped_column(String(255))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))


class Credential(TimestampMixin, Base):
    __tablename__ = "credentials"
    __table_args__ = (
        Index("ix_credentials_workspace_provider", "workspace_id", "provider"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[CredentialStatus] = mapped_column(
        enum_type(CredentialStatus, "credential_status"),
        default=CredentialStatus.ACTIVE,
        nullable=False,
    )
    encrypted_payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    encryption_key_id: Mapped[str] = mapped_column(String(500), nullable=False)


class UsageEvent(Base):
    __tablename__ = "usage_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_id", "workspace_id"],
            ["jobs.id", "jobs.workspace_id"],
            name="fk_usage_events_job_workspace",
            ondelete="RESTRICT",
        ),
        Index("ix_usage_events_workspace_created", "workspace_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    job_id: Mapped[UUID | None] = mapped_column(Uuid)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    metric: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
