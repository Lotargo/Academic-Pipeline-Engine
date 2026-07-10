# BE-02 — Session boundaries

## Decision

Production uses SQLAlchemy 2 with two session factories over the same schema:

- FastAPI request handlers use `AsyncSession` and an async PostgreSQL driver;
- Celery tasks use synchronous `Session` and a synchronous PostgreSQL driver.

The split follows the execution model of each process. API database I/O must
not block the event loop, while a Celery task must not create a private event
loop merely to access persistence. ORM mappings and SQL expressions are shared;
engine and session objects are process-local and are never shared between API
and worker containers.

SQLite remains a local-first/test adapter. Its implementation may be
synchronous behind the existing registry interface; production request code
must not select SQLite implicitly.

## Unit of work

One HTTP request or one Celery task attempt owns one session and at most one
active transaction at a time.

```text
API request -> AsyncSession -> begin -> repositories -> commit/rollback -> close
task attempt -> Session      -> begin -> repositories -> commit/rollback -> close
```

The composition root creates the session factory. A request dependency or task
wrapper creates and closes individual sessions. Domain services and
repositories receive a unit of work/session explicitly; they do not import a
global session.

## Transaction rules

- The outer request/task boundary owns `commit` and `rollback`.
- Repositories may `flush` to obtain identifiers or detect constraints but do
  not commit independently.
- Expected domain failures roll back before being translated to API/task
  results; unexpected exceptions also roll back and propagate.
- A task retry starts with a new session and transaction. No ORM object may be
  retained between attempts.
- Network calls, OCR, AI inference, and object uploads do not run while a
  database transaction is held open. Persist intent/state, commit, perform the
  external operation, then open a new short transaction to record the result.
- Job creation and its outbox event are written in the same transaction.
- Streaming responses and background callbacks cannot reuse the request
  session after the request dependency exits.

## Concurrency and loading

Sessions are not thread-safe or task-safe. Parallel coroutines or threads each
receive their own session. ORM entities must not be used as API schemas, queue
payloads, or cross-process state.

Relationships use explicit loading suitable for the use case; implicit lazy
I/O is forbidden in async request code. Tenant-owned repository operations
require an explicit `workspace_id` in addition to resource identifiers.

Locks, compare-and-set state transitions, counters, and outbox claiming may use
SQLAlchemy Core or reviewed SQL inside the same unit-of-work boundary.

## Lifecycle

API engines are created during application startup and disposed during
lifespan shutdown. Worker engines are created after the worker process starts,
not inherited through prefork. Tests create isolated factories and always
dispose them.

Connection URLs and pool settings come from configuration. Logs and exception
messages must not expose credentials embedded in a URL.

## Consequences for following tasks

- T002 provides async API and sync worker engine/session factories.
- T004 keeps transaction ownership in unit-of-work implementations and shares
  repository semantics across async PostgreSQL, sync PostgreSQL, and SQLite.
- T006 verifies commit, rollback, retry isolation, tenant filtering, and engine
  disposal for the relevant adapters.
