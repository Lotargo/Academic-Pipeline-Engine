from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class RetentionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    audit_event_days: int = Field(default=365, ge=1, le=3650)
    telemetry_event_seconds: int = Field(default=86_400, ge=60, le=2_592_000)
    telemetry_max_events: int = Field(default=512, ge=1, le=10_000)


class AlertThresholds(BaseModel):
    """Definitions only; a deployment adapter delivers the notifications."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_failures_per_window: int = Field(default=5, ge=1)
    provider_failure_window_seconds: int = Field(default=300, ge=60)
    job_stalled_seconds: int = Field(default=900, ge=60)
    worker_unavailable_seconds: int = Field(default=300, ge=60)


class MaintenanceSchedule(BaseModel):
    """Intervals consumed by the service worker/beat bootstrap."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    audit_pruning_seconds: int = Field(default=86_400, ge=3_600, le=2_592_000)


class ObservabilityConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = Field(default=1, ge=1)
    retention: RetentionPolicy = Field(default_factory=RetentionPolicy)
    alerts: AlertThresholds = Field(default_factory=AlertThresholds)
    maintenance: MaintenanceSchedule = Field(default_factory=MaintenanceSchedule)

    @classmethod
    def from_yaml(cls, path: str | Path = "config/observability.yaml") -> "ObservabilityConfig":
        file_path = Path(path)
        if not file_path.exists():
            return cls()
        raw = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
        return cls.model_validate(raw)
