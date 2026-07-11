# FE-10 route boundaries

| Runtime profile | Editor entry point | Create/status/cancel source |
|---|---|---|
| `service` (default) | `/` service editor | Workspace-scoped `/api/jobs`, snapshot and SSE routes |
| `local` (explicit `NEXT_PUBLIC_APE_RUNTIME_PROFILE=local`) | legacy editor | Local-first `/api/run`, `/api/status` and local artifacts |

`/cabinet/jobs?job=<id>` and `/?job=<id>` identify the same service Job. History
items use the service job ID for the editor link. The client never submits a
workspace ID; the backend derives it from the authenticated membership.

`editor_options` carries advanced editor choices in the Job payload. This keeps
the service UI independent from process-global `current_run`; pipeline execution
remains the worker/domain responsibility.
