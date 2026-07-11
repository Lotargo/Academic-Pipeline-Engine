# BE-12 walkthrough

## Scope

- Tasks: `BE-12-T001`–`BE-12-T007`
- Commit/PR: pending

## Delivered

- Added the owner-only two-step workspace cleanup contract and confirmation ledger.
- Deletes only one workspace's jobs, job metadata, artifacts and artifact keys.
- Keeps workspace identity, memberships, credentials and usage accounting intact;
  usage rows are detached from removed jobs.
- Records request and completion audit events, with one-way confirmation-token
  storage and idempotent completion.
- Kept legacy global history reset local-only; service mode returns `404`.

## Verification

- `.venv\\Scripts\\python.exe -m pytest tests/workspaces/test_cleanup.py tests/auth/test_auth_and_rbac.py tests/storage/test_artifact_storage.py -q`
- Result: `15 passed`.
- Covered owner authorization, cross-tenant indistinguishable `404`, explicit
  confirmation, artifact deletion, retention of other-workspace data, audit
  records, and repeat-safe completion.

## Deviation / next step

- No browser verification was run, per project rule. FE-09 should call the
  documented two-step API and present only the scoped cleanup copy.
