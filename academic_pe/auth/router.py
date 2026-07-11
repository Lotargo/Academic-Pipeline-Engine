from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Callable
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from academic_pe.auth.security import (AuthSettings, create_access_token, decode_access_token,
    hash_password, hash_refresh_token, new_refresh_token, verify_password)
from academic_pe.persistence.models import (ActorRole, LoginSession, Membership, MembershipRole,
    MembershipStatus, Organization, OrganizationKind, TenantStatus, User, UserStatus, Workspace)


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


def create_auth_router(session_factory: Callable[[], Session], settings: AuthSettings) -> APIRouter:
    router = APIRouter(prefix="/api/auth", tags=["auth"])

    def session_dep():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

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
        try:
            claims = decode_access_token(authorization[7:], settings)
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
