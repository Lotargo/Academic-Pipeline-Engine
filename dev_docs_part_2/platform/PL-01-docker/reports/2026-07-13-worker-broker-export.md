# PL-01 walkthrough — worker, broker and export images

- Date: 2026-07-13
- Tasks: PL-01-T003, T004, T007 (T001/T002/T005/T006 were already complete)
- Commit/PR: pending local review

## Delivered

- Reworked backend Dockerfile into dependency-builder, API and export targets.
  Runtime has no compiler/Poetry apt layer; LibreOffice exists only in export.
- Replaced the backend context deny-list with a strict allow-list, excluding
  generated UI, exports and env files from image builds.
- Added broker plus generation/research, export, maintenance workers and
  Celery Beat commands to service-dev Compose. RabbitMQ uses the official
  `rabbitmq:4.3.2-management-alpine` image and process-specific health checks.
- Added the Celery container entrypoint; its broker contract preserves only the
  existing ID-only workload queues: generation, research, export, maintenance;
  when the database URL is configured, Celery Beat also registers the existing
  scheduled audit-pruning task.
- `write_service_dev_env.py` now emits mock identity selection and a stable
  generated RabbitMQ password/broker URL; repeat runs retain that password.
- Root `docker-compose.yml` is now the same service-dev process matrix via
  Compose `extends`, so `docker compose up --build` does not start a competing
  legacy backend/frontend stack. Supabase remains a separate CLI-managed stack.
- Follow-up Compose validation corrected three process-wiring defects without
  changing the PL-04 topology: `migrate` and `backend` explicitly build the
  `api` target instead of Dockerfile's final `export` target; RabbitMQ 4.3 gets
  a versioned local compatibility config for Celery control/prefetch checks;
  Celery Beat has a process-specific liveness check instead of inheriting the
  API HTTP healthcheck.

## Verification

- `docker compose config --quiet` resolved the root entry point into broker,
  migration, API, frontend, three workers and scheduler; the explicit
  `--env-file .env.service-dev -f docker-compose.service-dev.yml` variant also
  passed.
- API target built as `academic-pe-api:pl01-check`: 662,093,089 bytes, user
  `ape` (UID 1001); in-container `/readyz` smoke passed.
- Frontend target built as `academic-pe-ui:pl01-check`: 219,813,121 bytes,
  user `ape`; its in-container `/login` health smoke returned `200`.
- Export target built as `academic-pe-export:pl01-check`: 1,066,405,238 bytes,
  user `ape`; `soffice --headless --version` returned LibreOffice 25.2.3.2.
- Celery image import exposed queues `export`, `generation`, `maintenance`,
  `research`; Docker process contract and queue regressions: 12 passed.
- Recreated `service-dev` against the CLI-managed Supabase stack: migration
  completed with exit `0`; broker, API, frontend, all three workers and Beat
  reached `healthy`; `/readyz` returned `200`.

## Notes

The 404MB export-image delta is intentionally isolated from API/workers.
RabbitMQ tag availability was checked against the Docker Official Image tags;
production should pin a platform-specific digest during deployment/CI policy.
