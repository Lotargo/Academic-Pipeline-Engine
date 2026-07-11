# FE-01 Auth API Contract

Browser-facing endpoints are same-origin Next.js route handlers. They proxy BE-03
and prevent refresh credentials from entering JavaScript-accessible storage.

## Browser API

- `POST /api/auth/register` — `{email,password}`; returns `{authenticated:true}`.
- `POST /api/auth/login` — `{email,password}`; returns `{authenticated:true}`.
- `GET /api/auth/session` — rotates the refresh session and returns auth state.
- `POST /api/auth/logout` — revokes the backend session and clears cookies.

Successful login/register/session responses set `ape_refresh` and `ape_access`
as `HttpOnly`, `SameSite=Lax` cookies (`Secure` in production). Logout and failed
restore clear both. The refresh value is never returned to browser JavaScript.

## Backend API

The handlers call BE-03 `/api/auth/{register,login,refresh,logout}`. BE-03 token
pairs stay server-side. Public errors use stable codes and do not relay backend
details: `invalid_credentials`, `account_blocked`, `email_unavailable`,
`validation_error`, and `service_unavailable`.
