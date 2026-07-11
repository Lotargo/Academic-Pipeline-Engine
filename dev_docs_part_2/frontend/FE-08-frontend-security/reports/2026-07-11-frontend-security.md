# FE-08 Frontend Security walkthrough

## Scope

- Composition: FE-08 Frontend Security.
- Tasks: T001–T007.

## Delivered

- Inventoried all application HTML/Markdown sinks in `SECURITY_INVENTORY.md`.
- Retained React-node-only Markdown rendering; static SVG CSS is the sole permitted
  static inline sink.
- Allow-listed chart CSS keys and color values before style interpolation.
- Added CSP and browser security headers without wildcard host sources.
- Added an API proxy that rejects declared cross-origin unsafe methods.
- Verified that access/refresh secrets are HttpOnly `SameSite=Lax` cookies and that
  browser storage contains only non-secret UI state.
- Enforced HTTPS plus `noopener noreferrer` for public payment/contact links.

## Verification

- `pnpm test:security` — passed (3 tests).
- `pnpm build` — passed.
- Production HTTP smoke test — cross-origin `POST /api/auth/login` returned 403;
  `/support` returned the CSP header.
- `git diff --check` — passed.

## Known limits

- Next.js still requires `unsafe-inline` for its current inline script/style output;
  a nonce-based CSP would require a separate runtime refactor.
- The CSRF proxy accepts non-browser service clients that omit both `Origin` and
  `Sec-Fetch-Site`; browser cross-origin unsafe requests carry an `Origin` and are
  rejected. `SameSite=Lax` cookies provide the additional browser-level boundary.
- Browser visual validation was not run, in accordance with the workspace rule.
