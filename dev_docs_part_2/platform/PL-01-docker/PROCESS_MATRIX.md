# PL-01 process matrix

## Purpose

`service-dev` is a Linux-first, reproducible integration environment. It runs
under Docker Engine in WSL2 now and must behave the same on a later Linux host.
It is not a production deployment and never receives production credentials.

## Container processes

| Process | Image | Command | Exposure | Readiness |
| --- | --- | --- | --- | --- |
| `frontend` | frontend runtime | `next start` | host `3000` | HTTP UI response |
| `api` | shared backend runtime | `uvicorn academic_pe.server:app` | host `8000` | `/readyz` |
| `migration` | shared backend runtime | `alembic upgrade head` | none; one-off | process exit `0` |
| `outbox-publisher` | shared backend runtime | publisher loop | internal | broker/DB connectivity |
| `worker` | shared backend runtime | Celery worker | internal | Celery ping/task registration |
| `maintenance` | shared backend runtime | Celery Beat | internal | scheduled task registration |
| `rabbitmq` | upstream image | broker | no default host port | native healthcheck |
| `export-worker` | optional backend extension | worker with LibreOffice | internal | worker readiness |

Every backend process uses the same application image but a distinct command.
No secret, source bind mount, user data or runtime state is baked into an image.

## Supabase local development

The target `service-dev` identity/data stack is the official local Supabase CLI
stack (`npx supabase init`, then `npx supabase start`) managed by Docker. It
provides local Auth, Postgres and Storage together; a standalone `postgres`
service is not a substitute.

Application containers must receive explicit, profile-specific values for the
local Supabase API gateway and database connection. Docker Desktop/WSL may use
`host.docker.internal`; the Linux compose profile must also support an explicit
host-gateway mapping or a shared external network. The exact connection values
are generated locally and remain in ignored env files.

The full self-hosted Supabase Docker distribution is deliberately not vendored
into APE's app compose: it models a separate production responsibility with its
own secrets, upgrades, backups and operations. `service-dev` uses the CLI
stack; a future self-hosted production decision is separate from `PL-01`.

## Current gap before worker activation

The queue domain contains Celery dispatch, transactional outbox and delivery
idempotency contracts, but no production `JobProcessor` mapping the persisted
`pipeline` job to the core pipeline. Until that adapter exists, a containerised
worker must not be claimed as able to execute user jobs. `PL-01` can build and
smoke-test the process image and broker topology, while the processor adapter
is tracked as a prerequisite for end-to-end service job execution.

## Verification target

1. `docker compose config` validates the process graph.
2. Images build under Linux Docker/WSL without host source mounts.
3. API and frontend readiness pass after the migration job completes.
4. RabbitMQ, outbox publisher, worker and maintenance process commands are
   separately inspectable; a successful job execution requires the processor
   adapter described above.

## Sources

- Supabase local development uses the official CLI Docker stack:
  [Supabase CLI](https://supabase.com/docs/guides/local-development/cli/getting-started).
- Full self-hosted Supabase has different operational responsibilities:
  [Self-hosting overview](https://supabase.com/docs/guides/self-hosting).
