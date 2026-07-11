from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from academic_pe.api_models import Attachment, ContinuationSource
from academic_pe.jobs.lifecycle import JobLifecycleRepository
from academic_pe.persistence.models import (Job, JobEvent, JobStage, JobStatus,
    Membership, MembershipStatus, TenantStatus, Workspace)
from academic_pe.queueing.dispatchers import Workload
from academic_pe.queueing.outbox import create_job_with_outbox


class JobCreateRequest(BaseModel):
    kind: str = "pipeline"
    topic: str = Field(min_length=1, max_length=500)
    instructions: str | None = Field(default=None, max_length=20_000)
    editor_options: "JobEditorOptions | None" = None


class JobEditorOptions(BaseModel):
    """Portable editor settings persisted with a service job, never global UI state."""
    academic_mode: bool = False
    author: str | None = Field(default=None, max_length=200)
    continuation_source: ContinuationSource | None = None
    artifact_override: str | None = Field(default=None, max_length=100)
    web_search_enabled: bool = False
    attachments: list[Attachment] = Field(default_factory=list)


def _job_payload(job: Job, stages: list[JobStage]) -> dict[str, Any]:
    return {
        "id": str(job.id), "kind": job.kind, "topic": job.payload.get("topic", ""),
        "instructions": job.payload.get("instructions"), "status": job.status.value,
        "editor_options": job.payload.get("editor_options"),
        "current_stage": job.current_stage, "progress": job.progress,
        "active_attempt": job.active_attempt,
        "cancel_requested_at": job.cancel_requested_at.isoformat() if job.cancel_requested_at else None,
        "error_code": job.error_code, "error_message": job.error_message,
        "created_at": job.created_at.isoformat(), "updated_at": job.updated_at.isoformat(),
        "stages": [{"name": stage.name, "status": stage.status, "progress": stage.progress} for stage in stages],
    }


def create_jobs_router(session_factory: Callable[[], Session], principal_dependency: Callable[..., Any]) -> APIRouter:
    """HTTP read/write adapter for persisted jobs; all workspace selection is server-side."""
    router = APIRouter(prefix="/api/jobs", tags=["jobs"])

    def session_dep():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def workspace_for_current(current: Any, session: Session) -> Workspace:
        workspace = session.scalar(select(Workspace).join(Membership).where(
            Membership.user_id == current.user_id,
            Membership.status == MembershipStatus.ACTIVE,
            Workspace.status == TenantStatus.ACTIVE,
        ).order_by(Workspace.created_at))
        if workspace is None:
            raise HTTPException(status_code=404, detail="workspace not found")
        return workspace

    def load_job(session: Session, workspace_id: UUID, job_id: UUID) -> Job:
        job = session.scalar(select(Job).where(Job.id == job_id, Job.workspace_id == workspace_id))
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return job

    def snapshot(session: Session, job: Job) -> dict[str, Any]:
        stages = session.scalars(select(JobStage).where(JobStage.job_id == job.id).order_by(JobStage.created_at)).all()
        return _job_payload(job, list(stages))

    @router.post("", status_code=201)
    def create_job(body: JobCreateRequest, current: Any = Depends(principal_dependency), session: Session = Depends(session_dep)):
        if body.kind != "pipeline":
            raise HTTPException(status_code=422, detail="unsupported job kind")
        workspace = workspace_for_current(current, session)
        payload = {"topic": body.topic.strip(), "instructions": body.instructions}
        if body.editor_options is not None:
            payload["editor_options"] = body.editor_options.model_dump(mode="json", exclude_none=True)
        job = create_job_with_outbox(session, workspace.id, current.user_id, body.kind, payload, Workload.GENERATION)
        session.add(JobEvent(job_id=job.id, event_type="job.created", data={"status": JobStatus.PENDING.value}))
        session.commit()
        return snapshot(session, job)

    @router.get("")
    def list_jobs(active: bool = Query(default=False), current: Any = Depends(principal_dependency), session: Session = Depends(session_dep)):
        workspace = workspace_for_current(current, session)
        statement = select(Job).where(Job.workspace_id == workspace.id).order_by(Job.created_at.desc())
        if active:
            statement = statement.where(Job.status.not_in([JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED]))
        jobs = session.scalars(statement).all()
        return {"jobs": [snapshot(session, job) for job in jobs]}

    @router.get("/{job_id}")
    def get_job(job_id: UUID, current: Any = Depends(principal_dependency), session: Session = Depends(session_dep)):
        workspace = workspace_for_current(current, session)
        return snapshot(session, load_job(session, workspace.id, job_id))

    @router.post("/{job_id}/cancel", status_code=202)
    def cancel_job(job_id: UUID, current: Any = Depends(principal_dependency), session: Session = Depends(session_dep)):
        workspace = workspace_for_current(current, session)
        job = JobLifecycleRepository(session).request_cancellation(job_id, workspace.id)
        session.commit()
        return snapshot(session, job)

    @router.get("/{job_id}/events")
    async def stream_events(job_id: UUID, last_event_id: str | None = None,
                            current: Any = Depends(principal_dependency), session: Session = Depends(session_dep)):
        workspace = workspace_for_current(current, session)
        load_job(session, workspace.id, job_id)
        session.close()

        try:
            resume_id = UUID(last_event_id) if last_event_id else None
        except ValueError:
            raise HTTPException(status_code=422, detail="invalid last_event_id")

        async def events():
            seen: set[UUID] = set()
            resume = resume_id
            while True:
                with session_factory() as event_session:
                    rows = event_session.scalars(select(JobEvent).where(JobEvent.job_id == job_id).order_by(JobEvent.created_at)).all()
                    if resume is not None:
                        for row in rows:
                            seen.add(row.id)
                            if row.id == resume:
                                resume = None
                                break
                    elif not seen:
                        seen.update(row.id for row in rows)
                    for row in rows:
                        if row.id in seen:
                            continue
                        job = event_session.get(Job, job_id)
                        if job is None:
                            return
                        seen.add(row.id)
                        payload = {"id": str(row.id), "type": row.event_type,
                                   "created_at": row.created_at.replace(tzinfo=UTC).isoformat(),
                                   "job": snapshot(event_session, job)}
                        yield f"id: {row.id}\nevent: message\ndata: {__import__('json').dumps(payload)}\n\n"
                await asyncio.sleep(1)

        return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    return router
