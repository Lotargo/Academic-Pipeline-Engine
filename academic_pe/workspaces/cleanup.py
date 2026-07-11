from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from academic_pe.persistence.models import (
    Artifact, AuditEvent, Job, JobAttempt, JobCheckpoint, JobEvent, JobStage,
    OutboxEvent, UsageEvent, WorkerDelivery, WorkspaceCleanupRequest,
    WorkspaceCleanupStatus,
)
from academic_pe.storage import ArtifactStorage


class CleanupNotFoundError(LookupError):
    """Use one error for missing resources and unauthorized tenant access."""


class CleanupConfirmationError(ValueError):
    pass


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class WorkspaceCleanupService:
    """Delete only disposable work data belonging to one authorized workspace.

    Credentials, usage accounting, memberships, and the workspace itself are retained.
    Storage removal happens before the database transaction: a failed object deletion
    leaves the request pending, and repeating the same confirmation safely resumes it.
    """

    def __init__(self, storage: ArtifactStorage):
        self.storage = storage

    def request(self, session: Session, workspace_id: UUID, user_id: UUID) -> tuple[WorkspaceCleanupRequest, str]:
        token = secrets.token_urlsafe(32)
        cleanup = WorkspaceCleanupRequest(
            workspace_id=workspace_id,
            requested_by_user_id=user_id,
            confirmation_token_hash=_token_hash(token),
        )
        session.add(cleanup)
        session.flush()
        session.add(AuditEvent(
            event_type="workspace.cleanup.requested",
            actor_user_id=user_id,
            metadata_json={"workspace_id": str(workspace_id), "cleanup_request_id": str(cleanup.id)},
        ))
        session.commit()
        return cleanup, token

    def complete(self, session: Session, workspace_id: UUID, user_id: UUID,
                 request_id: UUID, confirmation_token: str) -> WorkspaceCleanupRequest:
        cleanup = session.scalar(select(WorkspaceCleanupRequest).where(
            WorkspaceCleanupRequest.id == request_id,
            WorkspaceCleanupRequest.workspace_id == workspace_id,
            WorkspaceCleanupRequest.requested_by_user_id == user_id,
        ))
        if cleanup is None:
            raise CleanupNotFoundError
        if not secrets.compare_digest(cleanup.confirmation_token_hash, _token_hash(confirmation_token)):
            raise CleanupConfirmationError("invalid confirmation token")
        if cleanup.status == WorkspaceCleanupStatus.COMPLETED:
            return cleanup

        artifacts = session.scalars(select(Artifact).where(Artifact.workspace_id == workspace_id)).all()
        # ArtifactStorage authorizes every key against workspace_id before deleting it.
        for artifact in artifacts:
            self.storage.delete(workspace_id, artifact.storage_key)

        job_ids = select(Job.id).where(Job.workspace_id == workspace_id)
        outbox_ids = select(OutboxEvent.id).where(OutboxEvent.job_id.in_(job_ids))
        try:
            session.execute(delete(WorkerDelivery).where(WorkerDelivery.event_id.in_(outbox_ids)))
            session.execute(delete(OutboxEvent).where(OutboxEvent.job_id.in_(job_ids)))
            session.execute(delete(JobEvent).where(JobEvent.job_id.in_(job_ids)))
            session.execute(delete(JobCheckpoint).where(JobCheckpoint.job_id.in_(job_ids)))
            session.execute(delete(JobAttempt).where(JobAttempt.job_id.in_(job_ids)))
            session.execute(delete(JobStage).where(JobStage.job_id.in_(job_ids)))
            # Usage is retained for accounting, but can no longer reference deleted work.
            session.execute(update(UsageEvent).where(UsageEvent.workspace_id == workspace_id).values(job_id=None))
            session.execute(delete(Artifact).where(Artifact.workspace_id == workspace_id))
            session.execute(delete(Job).where(Job.workspace_id == workspace_id))
            cleanup.status = WorkspaceCleanupStatus.COMPLETED
            cleanup.completed_at = datetime.now(UTC)
            session.add(AuditEvent(
                event_type="workspace.cleanup.completed",
                actor_user_id=user_id,
                metadata_json={"workspace_id": str(workspace_id), "cleanup_request_id": str(cleanup.id)},
            ))
            session.commit()
        except Exception:
            session.rollback()
            raise
        return cleanup
