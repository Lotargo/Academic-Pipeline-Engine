# FE-10 Main Editor and Unified Jobs walkthrough

## Scope

- Composition: FE-10 Main Editor and Unified Jobs.
- Tasks: T001–T008.

## Delivered

- Extended the Job contract with typed `editor_options` and persisted it with the
  workspace Job payload.
- Added a shared create-job client and a profile-aware editor adapter.
- Added the service editor on `/`: it creates Jobs, loads snapshots, consumes
  SSE, requests cancellation and never reads global legacy status.
- Kept the legacy `/api/run` flow as the explicit `local` adapter.
- Added editor, cabinet-job and history deep links using one `job` query ID.
- Set profile variables in local/service-dev scripts for Windows and Unix.

## Verification

- `python -m pytest tests/jobs/test_job_api.py -q` — passed.
- `pnpm test:editor-jobs` — passed (3 tests).
- `pnpm build` — passed.
- `git diff --check` — passed.

## Notes

- Browser visual validation was not run, as required by the workspace rule.
- Service workers receive persisted `editor_options`; their pipeline execution
  semantics remain outside FE-10 and do not reintroduce a global `current_run`.
