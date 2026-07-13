"""Container entrypoint for Celery worker and Beat processes.

Business handlers remain registered by the service composition that owns a
workload.  This module deliberately contains no payload parsing or credentials:
the broker sees only the ID-only task contract from ``dispatchers``.
"""

from __future__ import annotations

import os

from academic_pe.observability.config import ObservabilityConfig
from academic_pe.persistence.config import DatabaseSettings, create_worker_engine, create_worker_session_factory
from academic_pe.queueing.dispatchers import create_celery_app
from academic_pe.queueing.maintenance import register_audit_pruning_task


broker_url = os.getenv("APE_BROKER_URL")
if not broker_url:
    raise RuntimeError("APE_BROKER_URL is required for a Celery worker process")

celery_app = create_celery_app(broker_url)

# Beat/maintenance has a concrete durable task.  Delivery handlers for the
# generation/export workloads are registered by their application composition;
# this module intentionally does not deserialize broker payloads itself.
if os.getenv("APE_DATABASE_SYNC_URL"):
    database_settings = DatabaseSettings.from_env()
    session_factory = create_worker_session_factory(create_worker_engine(database_settings))
    observability = ObservabilityConfig.from_yaml()
    register_audit_pruning_task(
        celery_app,
        session_factory,
        observability.retention,
        interval_seconds=observability.maintenance.audit_pruning_seconds,
    )
