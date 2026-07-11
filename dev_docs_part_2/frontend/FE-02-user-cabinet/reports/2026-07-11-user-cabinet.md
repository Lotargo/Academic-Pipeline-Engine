# FE-02 Walkthrough — User Cabinet

## Tasks

`FE-02-T001`–`FE-02-T007`.

## Result

- Added the protected `/cabinet` route group with a persistent responsive shell,
  accessible primary navigation, mobile menu, workspace header, and logout.
- Added a minimal authenticated `GET /api/auth/context` backend contract. It
  returns the caller's active workspace memberships only; the browser cannot
  supply or select a workspace to bypass backend membership checks.
- The same-origin session BFF refreshes the secure session and returns this
  context to the client. `SessionGate` exposes it through a React context only
  after successful restore; protected UI shows a loading state beforehand.
- Added a workspace overview with provider/resource summaries and honest empty
  states. Provider details remain intentionally deferred to FE-05.
- Added `/cabinet/settings` as the stable route boundary for the forthcoming
  provider-settings composition. Login and registration now lead to `/cabinet`.

## Verification

- `python -m pytest tests/auth/test_auth_and_rbac.py -q` — 4 passed, including
  ownership-scoped context.
- `node --test tests/auth-pages.mjs` — 4 passed, including the protected
  cabinet loading boundary.
- `npx tsc --noEmit` — passed.
- `node scripts/build.cjs` — passed; `/cabinet` and `/cabinet/settings` build.
- `git diff --check` — passed.
- Responsive behavior is a desktop sidebar plus a labelled mobile toggle;
  loading, no-workspace, and no-provider/resource states are accessible.

## Deviations and issues

- No commit or PR was requested or created.
- The prescribed `agent-browser` executable is not installed, so automated
  visual browser verification could not run. HTTP route tests and production
  build completed successfully.
- `pnpm build` first attempted to recreate dependencies and stopped at the
  workspace policy for an ignored `sharp` build script. The repository's actual
  build wrapper was then run directly and passed without altering dependencies.

## Next

Proceed to FE-03 Jobs and Live Status.
