from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from academic_pe.observability.config import RetentionPolicy
from academic_pe.persistence.models import AuditEvent


def prune_audit_events(
    session: Session,
    policy: RetentionPolicy,
    *,
    now: datetime | None = None,
) -> int:
    """Delete only expired audit rows; callers choose the scheduled adapter."""

    reference = now or datetime.now(UTC)
    cutoff = reference - timedelta(days=policy.audit_event_days)
    result = session.execute(delete(AuditEvent).where(AuditEvent.created_at < cutoff))
    return max(0, int(result.rowcount or 0))
