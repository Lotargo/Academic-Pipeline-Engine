from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from academic_pe.core.redaction import redact


class ObservabilityEvent(BaseModel):
    """Redacted, bounded event schema for logs and in-process metrics.

    The schema intentionally has no prompt, document content, credential, or
    raw request-body field.  Callers may record categorised diagnostics in
    ``details``; those are redacted again at the boundary.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_type: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,119}$")
    severity: Literal["debug", "info", "warning", "error"] = "info"
    correlation_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{7,127}$")
    source: str = Field(min_length=1, max_length=80)
    outcome: str = Field(default="unknown", min_length=1, max_length=40)
    job_id: str | None = Field(default=None, max_length=64)
    workspace_id: str | None = Field(default=None, max_length=64)
    actor_user_id: str | None = Field(default=None, max_length=64)
    details: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("details")
    @classmethod
    def redact_details(cls, value: dict[str, Any]) -> dict[str, Any]:
        sanitized = redact(value)
        return sanitized if isinstance(sanitized, dict) else {}


class AuditEventInput(BaseModel):
    """Audit intent kept distinct from normal debug/telemetry events."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_type: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,119}$")
    correlation_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{7,127}$")
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def redact_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        sanitized = redact(value)
        return sanitized if isinstance(sanitized, dict) else {}


def safe_audit_metadata(correlation_id: str, **metadata: Any) -> dict[str, Any]:
    """Add correlation without permitting credentials in persisted audit JSON."""

    return AuditEventInput(
        event_type="audit.event",
        correlation_id=correlation_id,
        metadata=metadata,
    ).metadata | {"correlation_id": correlation_id}


class StructuredEventFormatter(logging.Formatter):
    """Optional JSON formatter with message/extra redaction at emission time."""

    def format(self, record: logging.LogRecord) -> str:
        correlation_id = getattr(record, "correlation_id", None)
        if not isinstance(correlation_id, str) or len(correlation_id) < 8:
            correlation_id = "uncorrelated"
        payload = {
            "event_type": getattr(record, "event_type", "log.record"),
            "severity": record.levelname.casefold(),
            "correlation_id": correlation_id,
            "source": record.name,
            "outcome": getattr(record, "outcome", "unknown"),
            "message": redact(record.getMessage()),
        }
        return json.dumps(payload, ensure_ascii=False, default=str)
