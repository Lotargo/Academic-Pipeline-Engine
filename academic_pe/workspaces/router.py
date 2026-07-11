from __future__ import annotations

from typing import Any, Callable, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from academic_pe.persistence.models import Membership, MembershipRole, MembershipStatus, TenantStatus, Workspace
from academic_pe.storage import ArtifactStorage
from .cleanup import CleanupConfirmationError, CleanupNotFoundError, WorkspaceCleanupService


class CleanupRequestBody(BaseModel):
    confirmation: Literal["DELETE MY WORKSPACE DATA"]


class CleanupConfirmBody(BaseModel):
    confirmation_token: str = Field(min_length=32, max_length=1024)


class CleanupRequestResponse(BaseModel):
    id: UUID
    confirmation_token: str
    status: str


class CleanupResponse(BaseModel):
    id: UUID
    status: str


def create_workspace_cleanup_router(session_factory: Callable[[], Session],
                                    principal_dependency: Callable[..., Any],
                                    storage: ArtifactStorage) -> APIRouter:
    """Service-only API; callers must be active workspace owners."""
    router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])
    service = WorkspaceCleanupService(storage)

    def session_dep():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def require_owner(workspace_id: UUID, current: Any = Depends(principal_dependency),
                      session: Session = Depends(session_dep)) -> Membership:
        membership = session.scalar(select(Membership).join(Workspace).where(
            Membership.workspace_id == workspace_id,
            Membership.user_id == current.user_id,
            Membership.membership_role == MembershipRole.OWNER,
            Membership.status == MembershipStatus.ACTIVE,
            Workspace.status == TenantStatus.ACTIVE,
        ))
        if membership is None:
            raise HTTPException(status_code=404, detail="workspace not found")
        return membership

    @router.post("/{workspace_id}/cleanup-requests", response_model=CleanupRequestResponse, status_code=201)
    def create_request(_: CleanupRequestBody, workspace_id: UUID,
                       membership: Membership = Depends(require_owner),
                       session: Session = Depends(session_dep)):
        cleanup, token = service.request(session, workspace_id, membership.user_id)
        return CleanupRequestResponse(id=cleanup.id, confirmation_token=token, status=cleanup.status.value)

    @router.post("/{workspace_id}/cleanup-requests/{request_id}/confirm", response_model=CleanupResponse)
    def confirm_request(body: CleanupConfirmBody, workspace_id: UUID, request_id: UUID,
                        membership: Membership = Depends(require_owner),
                        session: Session = Depends(session_dep)):
        try:
            cleanup = service.complete(session, workspace_id, membership.user_id, request_id, body.confirmation_token)
        except CleanupNotFoundError:
            raise HTTPException(status_code=404, detail="workspace not found")
        except CleanupConfirmationError:
            raise HTTPException(status_code=400, detail="invalid cleanup confirmation")
        return CleanupResponse(id=cleanup.id, status=cleanup.status.value)

    return router
