# FE-12 walkthrough — provider auth mock flow

- Date: 2026-07-13
- Tasks: FE-12-T001–T006, T008 completed; T007 remains user-owned
- Commit/PR: pending local review

## Delivered

- Added the shared provider-auth contract and BFF adapter interface with
  explicit `mock` and `supabase` modes.
- Service login shows Google and Яндекс chooser only; mock mode is visibly
  marked and cannot be mistaken for production OAuth.
- Added `/auth/callback` complete/cancel/deny/provider-error states and
  server-side start/callback routes. Supabase mode uses PKCE cookie state and
  server-side code exchange; the Yandex provider alias is deployment config.
- Session restore, refresh and logout use HTTP-only first-party cookies;
  protected routes still require backend context verification.
- Excluded every `/api/auth/*` BFF route from the generic FastAPI rewrite.

## Verification

- Native WSL Node `v22.23.1`, pnpm `11.10.0`: production build passed.
- `pnpm run test:auth` → 5 passed.
- `pnpm run test:security` → 3 passed.

## Open gates

`FE-12-T007` is intentionally open: visual mock-flow smoke must be performed
by the user under project policy. Real Google/Яндекс OAuth E2E also remains
open until a permanent HTTPS deployment supplies Supabase redirects and
provider credentials. Neither mock UI nor these tests claim production OAuth.
