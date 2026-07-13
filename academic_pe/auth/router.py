from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import re
from typing import Annotated, Callable, Literal
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from academic_pe.auth.identity import (
    ExternalIdentityVerifier,
    IdentityProvisioningError,
    IdentityVerificationError,
    provision_external_identity,
)
from academic_pe.auth.security import (AuthSettings, create_access_token, decode_access_token,
    hash_password, hash_refresh_token, new_refresh_token, verify_password)
from academic_pe.observability import get_correlation_id, safe_audit_metadata
from academic_pe.persistence.models import (ActorRole, AuditEvent, Job, JobStatus, LoginSession, Membership,
    MembershipRole, MembershipStatus, Organization, OrganizationKind, OutboxEvent, TenantStatus,
    User, UserStatus, Workspace)
from academic_pe.providers import InMemoryProviderRegistry, ProviderHealth, ProviderRegistry
from academic_pe.providers.resources import BudgetKind, ResourceCoordinator


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=1024)


class RefreshRequest(BaseModel):
    refresh_token: str


class AdminInviteActivation(BaseModel):
    invite_token: str = Field(min_length=32, max_length=1024)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class Principal(BaseModel):
    user_id: UUID
    role: ActorRole


class WorkspaceContext(BaseModel):
    id: UUID
    name: str
    role: MembershipRole


class UserContext(BaseModel):
    user_id: UUID
    email: str
    role: ActorRole
    workspaces: list[WorkspaceContext]


class AdminUserSummary(BaseModel):
    id: UUID
    email: str
    role: ActorRole
    status: UserStatus
    created_at: datetime


class AdminResourceModel(BaseModel):
    id: str
    capabilities: list[str]


class KnownBudget(BaseModel):
    kind: Literal["known"]
    limit: Decimal
    used: Decimal


class UnknownBudget(BaseModel):
    kind: Literal["unknown"]


class AdminResourceProvider(BaseModel):
    id: str
    display_name: str
    models: list[AdminResourceModel]
    health: ProviderHealth
    availability: str
    supports_byok: bool
    platform_credential: None = None
    budget: KnownBudget | UnknownBudget


class FairUseContext(BaseModel):
    max_active_per_user: int
    max_queued_per_user: int


class AdminResourceSnapshot(BaseModel):
    providers: list[AdminResourceProvider]
    fair_use: FairUseContext
    generated_at: datetime


class AdminJobStatusCount(BaseModel):
    status: JobStatus
    count: int


class AdminQueueCount(BaseModel):
    workload: str
    pending: int
    retrying: int


class AdminJobsSnapshot(BaseModel):
    jobs: list[AdminJobStatusCount]
    queues: list[AdminQueueCount]
    generated_at: datetime


class AdminAuditEventSummary(BaseModel):
    id: UUID
    event_type: str
    actor_user_id: UUID | None
    target_user_id: UUID | None
    correlation_id: str | None
    created_at: datetime


class AdminAuditPage(BaseModel):
    events: list[AdminAuditEventSummary]
    limit: int
    offset: int
    next_offset: int | None


class AdminEventCount(BaseModel):
    event_type: str
    severity: Literal["debug", "info", "warning", "error"]
    outcome: str
    count: int = Field(ge=0)


class AdminHealthTelemetry(BaseModel):
    events_retained: int = Field(ge=0)
    http_requests: int = Field(ge=0)
    event_counts: list[AdminEventCount]


class AdminHealthSnapshot(BaseModel):
    status: Literal["ok"] = "ok"
    generated_at: datetime
    telemetry: AdminHealthTelemetry


_CORRELATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{7,127}$")


def create_auth_router(session_factory: Callable[[], Session], settings: AuthSettings | None = None,
                       provider_registry: ProviderRegistry | None = None,
                       resource_coordinator: ResourceCoordinator | None = None,
                       health_snapshot: Callable[[], dict[str, object]] | None = None,
                       *, identity_verifier: ExternalIdentityVerifier | None = None) -> APIRouter:
    """Create either the legacy JWT router or the service external-identity router.

    The two modes are mutually exclusive.  In particular, a service router
    never accepts an APE password JWT just because an old secret remains in an
    environment file.
    """

    if (settings is None) == (identity_verifier is None):
        raise ValueError("configure exactly one of legacy settings or an identity verifier")
    router = APIRouter(prefix="/api/auth", tags=["auth"])
    is_external_identity_mode = identity_verifier is not None
    provider_registry = provider_registry or InMemoryProviderRegistry()
    resource_coordinator = resource_coordinator or ResourceCoordinator()
    health_snapshot = health_snapshot or (lambda: {
        "events_retained": 0,
        "http_requests": 0,
        "event_counts": [],
    })

    def session_dep():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    if not is_external_identity_mode:
        assert settings is not None

        def issue(session: Session, user: User, login_session: LoginSession | None = None) -> TokenPair:
            raw = new_refresh_token()
            if login_session is None:
                login_session = LoginSession(user_id=user.id, token_hash=hash_refresh_token(raw),
                                             expires_at=datetime.now(UTC) + settings.refresh_ttl)
                session.add(login_session)
            else:
                login_session.token_hash = hash_refresh_token(raw)
                login_session.expires_at = datetime.now(UTC) + settings.refresh_ttl
            session.commit()
            return TokenPair(access_token=create_access_token(user.id, user.actor_role.value, user.token_version, settings),
                             refresh_token=raw)

        @router.post("/register", response_model=TokenPair, status_code=201)
        def register(body: Credentials, session: Session = Depends(session_dep)):
            user = User(email=str(body.email).lower(), password_hash=hash_password(body.password), actor_role=ActorRole.USER)
            try:
                session.add(user)
                session.flush()
                organization = Organization(owner_user_id=user.id, kind=OrganizationKind.PERSONAL, name="Personal")
                session.add(organization)
                session.flush()
                workspace = Workspace(organization_id=organization.id, name="Personal")
                session.add(workspace)
                session.flush()
                session.add(Membership(workspace_id=workspace.id, user_id=user.id, membership_role=MembershipRole.OWNER))
                session.flush()
            except IntegrityError:
                session.rollback()
                raise HTTPException(status_code=409, detail="email already registered")
            return issue(session, user)

        @router.post("/login", response_model=TokenPair)
        def login(body: Credentials, session: Session = Depends(session_dep)):
            user = session.scalar(select(User).where(User.email == str(body.email).lower()))
            if user is None or not verify_password(body.password, user.password_hash):
                raise HTTPException(status_code=401, detail="invalid credentials")
            if user.status != UserStatus.ACTIVE:
                raise HTTPException(status_code=403, detail="user is not active")
            return issue(session, user)

        @router.post("/refresh", response_model=TokenPair)
        def refresh(body: RefreshRequest, session: Session = Depends(session_dep)):
            login_session = session.scalar(select(LoginSession).where(LoginSession.token_hash == hash_refresh_token(body.refresh_token)))
            now = datetime.now(UTC)
            if login_session is None or login_session.revoked_at is not None or login_session.expires_at.replace(tzinfo=UTC) <= now:
                raise HTTPException(status_code=401, detail="invalid refresh token")
            user = session.get(User, login_session.user_id)
            if user is None or user.status != UserStatus.ACTIVE:
                raise HTTPException(status_code=403, detail="user is not active")
            return issue(session, user, login_session)

        @router.post("/logout", status_code=204)
        def logout(body: RefreshRequest, session: Session = Depends(session_dep)):
            login_session = session.scalar(select(LoginSession).where(LoginSession.token_hash == hash_refresh_token(body.refresh_token)))
            if login_session is not None and login_session.revoked_at is None:
                login_session.revoked_at = datetime.now(UTC)
                session.commit()

    def principal(authorization: Annotated[str | None, Header()] = None, session: Session = Depends(session_dep)) -> Principal:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="missing bearer token")
        bearer_token = authorization[7:]
        if identity_verifier is not None:
            try:
                identity = identity_verifier.verify(bearer_token)
                user = provision_external_identity(session, identity)
            except IdentityVerificationError:
                raise HTTPException(status_code=401, detail="invalid external identity token")
            except IdentityProvisioningError:
                raise HTTPException(status_code=409, detail="external identity cannot be provisioned")
            if user.status != UserStatus.ACTIVE:
                raise HTTPException(status_code=403, detail="user is not active")
            return Principal(user_id=user.id, role=user.actor_role)
        try:
            assert settings is not None
            claims = decode_access_token(bearer_token, settings)
            user = session.get(User, UUID(claims["sub"]))
        except (jwt.InvalidTokenError, KeyError, ValueError):
            raise HTTPException(status_code=401, detail="invalid access token")
        if user is None or user.status != UserStatus.ACTIVE or user.token_version != claims.get("ver"):
            raise HTTPException(status_code=401, detail="invalid access token")
        return Principal(user_id=user.id, role=user.actor_role)

    def require_admin(current: Principal = Depends(principal)) -> Principal:
        if current.role != ActorRole.ADMIN:
            raise HTTPException(status_code=403, detail="admin role required")
        return current

    def audit_admin_view(session: Session, actor_user_id: UUID, event_type: str) -> None:
        correlation_id = get_correlation_id() or "service_00000000"
        session.add(AuditEvent(
            event_type=event_type,
            actor_user_id=actor_user_id,
            metadata_json=safe_audit_metadata(correlation_id),
        ))
        session.commit()

    def safe_correlation_id(metadata: object) -> str | None:
        if not isinstance(metadata, dict):
            return None
        value = metadata.get("correlation_id")
        return value if isinstance(value, str) and _CORRELATION_ID_PATTERN.fullmatch(value) else None

    @router.get("/context", response_model=UserContext)
    def context(current: Principal = Depends(principal), session: Session = Depends(session_dep)):
        """Return only the caller's active workspace memberships for the cabinet."""
        user = session.get(User, current.user_id)
        memberships = session.execute(
            select(Membership, Workspace)
            .join(Workspace, Workspace.id == Membership.workspace_id)
            .where(
                Membership.user_id == current.user_id,
                Membership.status == MembershipStatus.ACTIVE,
                Workspace.status == TenantStatus.ACTIVE,
            )
            .order_by(Workspace.created_at)
        ).all()
        return UserContext(
            user_id=current.user_id,
            email=user.email,
            role=current.role,
            workspaces=[
                WorkspaceContext(id=workspace.id, name=workspace.name, role=membership.membership_role)
                for membership, workspace in memberships
            ],
        )

    @router.get("/admin/users", response_model=list[AdminUserSummary])
    def admin_users(_: Principal = Depends(require_admin), session: Session = Depends(session_dep)):
        """List user metadata for an administrator; credentials and sessions are never exposed."""
        users = session.scalars(select(User).order_by(User.created_at.desc(), User.email)).all()
        return [AdminUserSummary(id=user.id, email=user.email, role=user.actor_role,
                                 status=user.status, created_at=user.created_at) for user in users]

    @router.get("/admin/resources", response_model=AdminResourceSnapshot)
    def admin_resources(_: Principal = Depends(require_admin)):
        providers: list[AdminResourceProvider] = []
        for definition in provider_registry.list():
            state = resource_coordinator.budget(definition.id)
            budget: KnownBudget | UnknownBudget
            if state.kind == BudgetKind.KNOWN:
                budget = KnownBudget(kind="known", limit=state.limit, used=state.used)
            else:
                budget = UnknownBudget(kind="unknown")
            providers.append(AdminResourceProvider(
                id=definition.id, display_name=definition.display_name or definition.id,
                models=[AdminResourceModel(id=model.id, capabilities=sorted(capability.value for capability in model.capabilities))
                        for model in definition.models], health=ProviderHealth.UNKNOWN,
                availability=state.availability.value, supports_byok=definition.requires_credential,
                budget=budget,
            ))
        return AdminResourceSnapshot(
            providers=providers,
            fair_use=FairUseContext(max_active_per_user=resource_coordinator.policy.max_active_per_user,
                                    max_queued_per_user=resource_coordinator.policy.max_queued_per_user),
            generated_at=datetime.now(UTC),
        )

    @router.get("/admin/jobs", response_model=AdminJobsSnapshot)
    def admin_jobs(_: Principal = Depends(require_admin), session: Session = Depends(session_dep)):
        """Return aggregate queue and lifecycle state without exposing job payloads."""
        status_counts = {status: 0 for status in JobStatus}
        for status, count in session.execute(select(Job.status, func.count(Job.id)).group_by(Job.status)):
            status_counts[status] = count
        queue_rows = session.execute(
            select(
                OutboxEvent.workload,
                func.count(OutboxEvent.id),
                func.coalesce(func.sum(OutboxEvent.attempts > 0), 0),
            )
            .where(OutboxEvent.published_at.is_(None))
            .group_by(OutboxEvent.workload)
            .order_by(OutboxEvent.workload)
        )
        return AdminJobsSnapshot(
            jobs=[AdminJobStatusCount(status=status, count=count) for status, count in status_counts.items()],
            queues=[AdminQueueCount(workload=workload, pending=pending, retrying=retrying)
                    for workload, pending, retrying in queue_rows],
            generated_at=datetime.now(UTC),
        )

    @router.get("/admin/audit-events", response_model=AdminAuditPage)
    def admin_audit_events(
        current: Principal = Depends(require_admin),
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=10_000),
        session: Session = Depends(session_dep),
    ):
        """Return a bounded, metadata-free audit page to an administrator only."""

        rows = session.scalars(
            select(AuditEvent)
            .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
            .offset(offset)
            .limit(limit + 1)
        ).all()
        page = rows[:limit]
        audit_admin_view(session, current.user_id, "admin.audit.viewed")
        return AdminAuditPage(
            events=[
                AdminAuditEventSummary(
                    id=row.id,
                    event_type=row.event_type,
                    actor_user_id=row.actor_user_id,
                    target_user_id=row.target_user_id,
                    correlation_id=safe_correlation_id(row.metadata_json),
                    created_at=row.created_at,
                )
                for row in page
            ],
            limit=limit,
            offset=offset,
            next_offset=offset + len(page) if len(rows) > limit else None,
        )

    @router.get("/admin/health", response_model=AdminHealthSnapshot)
    def admin_health(current: Principal = Depends(require_admin), session: Session = Depends(session_dep)):
        """Expose only aggregate, redacted process health counters to admins."""

        try:
            telemetry = AdminHealthTelemetry.model_validate(health_snapshot())
        except Exception:
            raise HTTPException(status_code=503, detail="health information unavailable") from None
        audit_admin_view(session, current.user_id, "admin.health.viewed")
        return AdminHealthSnapshot(generated_at=datetime.now(UTC), telemetry=telemetry)

    def require_workspace(workspace_id: UUID, current: Principal = Depends(principal), session: Session = Depends(session_dep)) -> Membership:
        membership = session.scalar(select(Membership).join(Workspace).where(
            Membership.workspace_id == workspace_id, Membership.user_id == current.user_id,
            Membership.status == MembershipStatus.ACTIVE, Workspace.status == TenantStatus.ACTIVE))
        if membership is None:
            raise HTTPException(status_code=404, detail="workspace not found")
        return membership

    @router.post("/admin-invites/activate", status_code=204)
    def activate_admin(body: AdminInviteActivation, current: Principal = Depends(principal),
                       session: Session = Depends(session_dep)):
        from academic_pe.admin_bootstrap import BootstrapError, activate_admin_invite
        try:
            activate_admin_invite(session, current.user_id, body.invite_token)
        except BootstrapError:
            raise HTTPException(status_code=400, detail="invalid or expired admin invite")

    router.principal_dependency = principal  # type: ignore[attr-defined]
    router.admin_dependency = require_admin  # type: ignore[attr-defined]
    router.workspace_dependency = require_workspace  # type: ignore[attr-defined]
    return router
