# BE-03 token and authorization model

- Passwords use pwdlib's recommended Argon2 hash; public registration enforces 12 characters.
- Access tokens are short-lived HS256 JWTs containing `sub`, `role`, `ver`, `typ`, issuer and timestamps.
- Refresh tokens are opaque 384-bit random values. Only their SHA-256 digest is persisted.
- Refresh rotates the stored digest atomically; reuse of the preceding token fails.
- Logout sets `revoked_at`. Incrementing `users.token_version` invalidates every existing access JWT.
- Blocked/deleted users cannot login, refresh, or authenticate an access JWT.
- Global role and workspace membership are separate checks. Active membership and active workspace are required.
- Missing tenant access returns 404 to avoid exposing workspace existence.
- Public registration always assigns `user`; administrator assignment belongs to BE-04.

Service mode requires `APE_DATABASE_ASYNC_URL`, `APE_DATABASE_SYNC_URL`, and a
minimum 32-character `APE_AUTH_JWT_SECRET`. Without database configuration the
legacy local-first server remains unchanged.
