# FE-04 walkthrough — 2026-07-11

## Tasks

`FE-04-T001`–`FE-04-T008`.

## Done

- Added the tenant-scoped history/artifact HTTP contract at
  `dev_docs_part_2/contracts/history-artifact-api.md`.
- Added `/cabinet/history`, status filter, cursor-based loading, item details
  and artifact metadata.
- Added authenticated Next proxy routes for history, archive/delete and signed
  artifact-download requests.
- A signed URL is requested only on explicit download; it is not persisted.
- Archive/delete use explicit confirmation. Empty, API-error, unavailable
  detail and expired-link (`410`) states are presented to the user.

## Verification

- `node --test tests/history-contract.mjs`
- `node_modules/.bin/tsc --noEmit`
- `node scripts/build.cjs`
- `git diff --check`

## Deviation / follow-up

The legacy local-first FastAPI history endpoints are not used as the service
contract. The service backend must implement the recorded tenant-scoped
endpoints, including membership checks and signed URLs, before deployed E2E
tests can run. This frontend adapter intentionally contains no storage keys or
workspace identifiers.
