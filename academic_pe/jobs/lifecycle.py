from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from academic_pe.persistence.models import (AttemptStatus, Job, JobAttempt, JobCheckpoint,
    JobEvent, JobStage, JobStatus)


class InvalidJobTransition(ValueError):
    pass


TRANSITIONS = {
    JobStatus.PENDING: {JobStatus.QUEUED, JobStatus.CANCELLED},
    JobStatus.QUEUED: {JobStatus.RUNNING, JobStatus.CANCELLED},
    JobStatus.RUNNING: {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.QUEUED},
    JobStatus.FAILED: {JobStatus.QUEUED},
    JobStatus.SUCCEEDED: set(),
    JobStatus.CANCELLED: set(),
}


class JobLifecycleRepository:
    def __init__(self, session: Session):
        self.session = session

    def _job(self, job_id: UUID, workspace_id: UUID, lock: bool = True) -> Job:
        query = select(Job).where(Job.id == job_id, Job.workspace_id == workspace_id)
        if lock:
            query = query.with_for_update()
        job = self.session.scalar(query)
        if job is None:
            raise KeyError("job not found")
        return job

    def _event(self, job: Job, event_type: str, **data: object) -> None:
        self.session.add(JobEvent(job_id=job.id, event_type=event_type, data=data))

    def transition(self, job_id: UUID, workspace_id: UUID, target: JobStatus,
                   *, error_code: str | None = None, error_message: str | None = None) -> Job:
        job = self._job(job_id, workspace_id)
        if job.status == target:
            return job
        if target not in TRANSITIONS[job.status]:
            raise InvalidJobTransition(f"{job.status.value} -> {target.value}")
        previous = job.status
        job.status = target
        job.error_code, job.error_message = error_code, error_message
        if target in {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED}:
            job.heartbeat_at = None
        self._event(job, "job.transitioned", previous=previous.value, current=target.value)
        self.session.flush()
        return job

    def begin_attempt(self, job_id: UUID, workspace_id: UUID, worker_id: str) -> JobAttempt:
        job = self.transition(job_id, workspace_id, JobStatus.RUNNING)
        now = datetime.now(UTC)
        job.active_attempt += 1
        job.heartbeat_at = now
        attempt = JobAttempt(job_id=job.id, number=job.active_attempt,
                             status=AttemptStatus.RUNNING, started_at=now, worker_id=worker_id)
        self.session.add(attempt)
        self._event(job, "job.attempt.started", number=attempt.number, worker_id=worker_id)
        self.session.flush()
        return attempt

    def heartbeat(self, job_id: UUID, workspace_id: UUID, worker_id: str) -> None:
        job = self._job(job_id, workspace_id)
        if job.status != JobStatus.RUNNING:
            raise InvalidJobTransition("heartbeat requires running job")
        attempt = self.session.scalar(select(JobAttempt).where(
            JobAttempt.job_id == job.id, JobAttempt.number == job.active_attempt))
        if attempt is None or attempt.worker_id != worker_id:
            raise InvalidJobTransition("heartbeat worker does not own active attempt")
        job.heartbeat_at = datetime.now(UTC)
        self.session.flush()

    def complete_attempt(self, job_id: UUID, workspace_id: UUID, target: JobStatus,
                         *, error_code: str | None = None, error_message: str | None = None) -> Job:
        if target not in {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED}:
            raise InvalidJobTransition("attempt can only complete with a terminal status")
        job = self._job(job_id, workspace_id)
        attempt = self.session.scalar(select(JobAttempt).where(
            JobAttempt.job_id == job.id, JobAttempt.number == job.active_attempt))
        if attempt is None:
            raise InvalidJobTransition("active attempt not found")
        if attempt.status != AttemptStatus.RUNNING:
            if job.status == target:
                return job
            raise InvalidJobTransition("active attempt already completed")
        result = self.transition(job_id, workspace_id, target,
                                 error_code=error_code, error_message=error_message)
        attempt.status = AttemptStatus.SUCCEEDED if target == JobStatus.SUCCEEDED else AttemptStatus.FAILED
        if target == JobStatus.CANCELLED:
            attempt.status = AttemptStatus.INTERRUPTED
        attempt.finished_at = datetime.now(UTC)
        self._event(job, "job.attempt.completed", number=attempt.number, status=attempt.status.value)
        self.session.flush()
        return result

    def update_stage(self, job_id: UUID, workspace_id: UUID, name: str, progress: int) -> JobStage:
        if not 0 <= progress <= 100:
            raise ValueError("progress must be between 0 and 100")
        job = self._job(job_id, workspace_id)
        if job.status != JobStatus.RUNNING:
            raise InvalidJobTransition("stage update requires running job")
        stage = self.session.scalar(select(JobStage).where(JobStage.job_id == job.id, JobStage.name == name))
        now = datetime.now(UTC)
        if stage is None:
            stage = JobStage(job_id=job.id, name=name, status="pending", progress=0, started_at=now)
            self.session.add(stage)
        stage.progress = max(stage.progress, progress)
        stage.status = "succeeded" if stage.progress == 100 else "running"
        if stage.progress == 100:
            stage.completed_at = now
        job.current_stage, job.progress = name, stage.progress
        self._event(job, "job.stage.updated", stage=name, progress=stage.progress)
        self.session.flush()
        return stage

    def save_checkpoint(self, job_id: UUID, workspace_id: UUID, stage: str,
                        payload: dict) -> JobCheckpoint:
        job = self._job(job_id, workspace_id)
        checkpoint = self.session.scalar(select(JobCheckpoint).where(
            JobCheckpoint.job_id == job.id, JobCheckpoint.stage == stage))
        if checkpoint is None:
            checkpoint = JobCheckpoint(job_id=job.id, stage=stage, payload=payload,
                                       attempt_number=job.active_attempt)
            self.session.add(checkpoint)
        else:
            checkpoint.payload = payload
            checkpoint.attempt_number = job.active_attempt
        self._event(job, "job.checkpoint.saved", stage=stage)
        self.session.flush()
        return checkpoint

    def checkpoint(self, job_id: UUID, workspace_id: UUID, stage: str) -> JobCheckpoint | None:
        job = self._job(job_id, workspace_id, lock=False)
        return self.session.scalar(select(JobCheckpoint).where(
            JobCheckpoint.job_id == job.id, JobCheckpoint.stage == stage))

    def request_cancellation(self, job_id: UUID, workspace_id: UUID) -> Job:
        job = self._job(job_id, workspace_id)
        if job.status in {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED}:
            return job
        if job.cancel_requested_at is None:
            job.cancel_requested_at = datetime.now(UTC)
            self._event(job, "job.cancellation.requested")
            self.session.flush()
        return job

    def acknowledge_cancellation(self, job_id: UUID, workspace_id: UUID) -> Job:
        job = self._job(job_id, workspace_id)
        if job.status == JobStatus.CANCELLED:
            return job
        if job.cancel_requested_at is None:
            raise InvalidJobTransition("cancellation was not requested")
        return self.transition(job_id, workspace_id, JobStatus.CANCELLED)

    def recover_interrupted(self, stale_after: timedelta) -> list[UUID]:
        cutoff = datetime.now(UTC) - stale_after
        jobs = self.session.scalars(select(Job).where(
            Job.status == JobStatus.RUNNING, Job.heartbeat_at < cutoff).with_for_update()).all()
        recovered = []
        now = datetime.now(UTC)
        for job in jobs:
            attempt = self.session.scalar(select(JobAttempt).where(
                JobAttempt.job_id == job.id, JobAttempt.number == job.active_attempt))
            if attempt is not None and attempt.status == AttemptStatus.RUNNING:
                attempt.status, attempt.finished_at = AttemptStatus.INTERRUPTED, now
            job.status, job.heartbeat_at = JobStatus.QUEUED, None
            self._event(job, "job.interrupted.requeued", attempt=job.active_attempt)
            recovered.append(job.id)
        self.session.flush()
        return recovered
