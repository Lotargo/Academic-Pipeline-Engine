# BE-13 walkthrough — Supabase identity adapter

- Date: 2026-07-13
- Tasks: BE-13-T001 through BE-13-T007
- Commit/PR: pending local review

## Delivered

- Added the shared [provider-only auth contract](../../../contracts/provider-auth.md).
- Added `external_identities` migration and idempotent user, personal
  workspace and membership provisioning keyed by immutable issuer/subject.
- Added a visibly development-only mock verifier and a Supabase JWT verifier
  with asymmetric signature, issuer, audience, expiry, authenticated-role,
  provider and normalized-email validation. Unknown `kid` has one bounded JWKS
  refresh and then fails closed.
- Service startup now selects exactly one adapter: `legacy`, `mock` or
  `supabase`. External modes do not mount password/register/refresh/logout
  endpoints; local-first stays outside the database-enabled service branch.
- Existing application RBAC and workspace checks run after identity resolution.

## Verification

- `pytest tests/auth/test_supabase_identity.py tests/auth/test_auth_and_rbac.py
  tests/jobs/test_job_api.py tests/workspaces/test_cleanup.py -q` → 15 passed.
- Targeted queue/container identity regression → 12 passed.
- `python -m compileall -q academic_pe` passed.
- Full Python regression: `679 passed, 3 skipped`.

## Production OAuth gate

Only mock adapter and offline JWT/JWKS contracts were verified. A permanent
HTTPS frontend/API URL, Supabase Cloud `SITE_URL` and exact redirects, provider
applications, protected secrets and Google/Яндекс E2E are still required before
setting `APE_IDENTITY_ADAPTER=supabase` in production.
