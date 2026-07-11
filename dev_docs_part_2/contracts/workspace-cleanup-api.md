# Workspace cleanup API contract

Service mode exposes a two-step, owner-only workflow. `workspace_id` is a route
parameter and is authorized against the authenticated principal on the server;
it is never accepted from an untrusted request body.

## Create confirmation

`POST /api/workspaces/{workspace_id}/cleanup-requests`

```json
{"confirmation":"DELETE MY WORKSPACE DATA"}
```

Returns `201` with a request ID and a one-time `confirmation_token`. The token
is returned only in this response and persisted solely as a SHA-256 digest.

## Complete cleanup

`POST /api/workspaces/{workspace_id}/cleanup-requests/{request_id}/confirm`

```json
{"confirmation_token":"<token returned by create>"}
```

Returns the request ID and `pending` or `completed` status. Repeating a valid
completion after success returns the same `completed` state.

Only active `owner` memberships may call either endpoint. Missing workspace,
foreign workspace and foreign request all return `404`, avoiding tenant
existence disclosure. Invalid confirmations return `400`.

The cleanup removes the selected workspace's jobs, job metadata, artifacts and
their object-storage keys. It retains the workspace, memberships, credentials,
and usage accounting (with `usage_events.job_id` detached). Both request and
completion create audit events. A storage failure leaves the request pending;
retrying the same confirmation resumes safely because artifact deletes are
idempotent.

## Local-first boundary

`POST /api/history/reset` remains a legacy local-only maintenance endpoint. In
service mode it returns `404`; the frontend must use this scoped contract and
must not offer a global reset.
