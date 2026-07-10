# BE-07 job state and recovery model

## State machine

```text
pending -> queued -> running -> succeeded
   |          |         |  \-> failed -> queued (explicit retry)
   |          |         \----> queued (interrupted recovery)
   \----------+--------------> cancelled
```

Terminal states are `succeeded` and `cancelled`. Repeating the same transition is
idempotent; every different invalid transition is rejected. Failed jobs retry
only through an explicit `failed -> queued` transition.

## Durable records

- `jobs`: current status/stage/progress, attempt number, heartbeat and cancellation.
- `job_stages`: monotonic progress per named stage.
- `job_attempts`: worker ownership and terminal/interrupted outcome.
- `job_events`: append-only lifecycle history for API/live view.
- `job_checkpoints`: one updatable recovery payload per job/stage.

All repository operations require both `job_id` and `workspace_id`. Mutations use
row locking where supported and commit at the request/worker UoW boundary.

## Recovery policy

Workers heartbeat only while running and only for their active attempt. A
maintenance process selects running jobs older than its stale threshold, marks
the attempt interrupted and requeues the job. The next attempt reads the latest
checkpoint for its stage and resumes after the last durable unit. Checkpoints are
written only after externally visible output is safely persisted.

Cancellation is two-phase: API records a request idempotently; the worker stops
at a safe boundary, persists a checkpoint if needed, then acknowledges cancelled.
