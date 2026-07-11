# FE-01 Walkthrough — Auth Pages

## Tasks

`FE-01-T001`–`FE-01-T007`.

## Result

- Added `/login` and `/register` mobile-first pages with labelled fields,
  password visibility control, pending state, and generic public errors.
- Added same-origin BFF handlers for login, registration, session restore, and
  logout. Refresh and access tokens use `HttpOnly`, `SameSite=Lax` cookies;
  JavaScript receives only `{authenticated}` state.
- Session restore rotates the backend refresh token. Missing, expired, blocked,
  and unavailable states redirect to login with an appropriate public message.
- Added logout to the existing account menu and redirect to the current cabinet
  route (`/`) after successful authentication.
- Documented the browser/backend auth boundary in `AUTH_API_CONTRACT.md`.

## Verification

- `node_modules/.bin/tsc.CMD --noEmit` — passed.
- `node scripts/build.cjs` (`next build --webpack`) — passed; all auth routes
  generated. Turbopack could not resolve remote Google Font assets in this
  environment, so the existing build wrapper now selects webpack explicitly.
- `node --test tests/auth-pages.mjs` — 3 passed: login markup, registration
  without role selection, and missing-cookie restore.
- Responsive layout uses a 390px-safe mobile-first shell and fluid `max-w-md`
  card. Labels, input types, autocomplete, focusable controls, live loading text,
  and alert roles were checked in implementation.
- Automated visual browser verification was attempted, but the prescribed
  `agent-browser` executable is not installed in this workspace.

## Deviations and issues

- No commit or PR was requested or created.
- Initial manual registration failed because the local backend was started without
  `APE_DATABASE_SYNC_URL`, `APE_DATABASE_ASYNC_URL`, and `APE_AUTH_JWT_SECRET`;
  in that legacy mode the auth router is intentionally not mounted. The standalone
  `ape-dev-postgres` container was also stopped.
- PostgreSQL was restarted, migrations were applied, and the complete BFF request
  `POST /api/auth/register` was verified with `201`, auth cookies, and
  `{authenticated:true}`.
- The user confirmed the PostgreSQL-backed registration, login, session, and
  logout browser flow works correctly on 2026-07-11.
- The configured lint command could not run because this workspace currently has
  no installed `eslint` executable; no lint result is claimed.

## Next

Proceed to FE-02 User Cabinet.
