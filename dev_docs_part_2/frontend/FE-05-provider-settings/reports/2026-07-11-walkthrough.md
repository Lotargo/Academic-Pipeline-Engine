# FE-05 walkthrough — 2026-07-11

## Tasks

`FE-05-T001`–`FE-05-T008`.

## Done

- Added the tenant-scoped provider settings and credential contract at
  `dev_docs_part_2/contracts/provider-settings-api.md`.
- Replaced the settings placeholder with provider/model selection, clear
  platform/BYOK policies and availability messages that never show a numeric
  quota for an unknown resource.
- Added authenticated Next proxy routes for provider settings and credential
  create/replace/delete operations.
- Added safe credential UI: password inputs, fixed masking, metadata-only
  rendering, validation state, explicit replacement and deletion actions.
- Added a component/contract security test; it verifies masking, absence of
  browser persistence, explicit deletion and authenticated mutation routes.

## Verification

- `node --test tests/provider-settings-contract.mjs`
- `node_modules/.bin/tsc --noEmit`
- `node scripts/build.cjs`
- `TEST_BASE_URL=http://127.0.0.1:3000 node --test tests/auth-pages.mjs tests/jobs-api.mjs tests/history-contract.mjs tests/provider-settings-contract.mjs`
- `git diff --check`

## Deviation / follow-up

The current service FastAPI app does not yet implement the documented
`/api/provider-settings` and `/api/credentials` HTTP adapters. The frontend
routes intentionally proxy the recorded tenant-scoped contract and show a safe
unavailable state until that backend adapter is deployed; they never fall back
to the legacy local secrets API.

Visual browser verification was intentionally left to the user because the
application has a known browser-check instability. No claim of visual E2E
verification is made in this walkthrough.
