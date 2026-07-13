# PL-04 — Linux-first service-dev walkthrough

## Result

`service-dev` is reproducible with the official local Supabase CLI/Docker
stack and a separate APE Compose project. The source configuration is versioned;
runtime endpoint values and the temporary legacy compatibility secret are written
only to ignored `.env.service-dev`.

The workflow intentionally starts Auth, Postgres, Storage and the API gateway.
It excludes optional `logflare` and `vector`: on the tested Docker Desktop/WSL
bridge Vector cannot read the Docker socket, while those services are not needed
for local Auth/Postgres/Storage verification.

## Commands and checks

PowerShell entry point:

```powershell
.\run-service-dev.bat
.\run-service-dev.bat status
```

POSIX/WSL entry point:

```bash
./run-service-dev.sh
./run-service-dev.sh status
```

For the Linux smoke, a clean Git checkout was used from
`/home/etotm/projects/Academic-Pipeline-Engine` (WSL ext4), rather than a
Windows-mounted source directory. WSL used native Node `v22.23.1` and its native
`npx`; the script prioritises `$HOME/.local/node/bin/npx` when present.

The clean checkout performed a fresh frontend Docker build, then Compose ran:

1. `migrate` from the shared backend image;
2. API after `migrate` exited successfully;
3. frontend after the API healthcheck became healthy.

Observed results, with local keys omitted:

- Supabase Auth health: HTTP 200;
- Supabase REST gateway: HTTP 200;
- Supabase Postgres probe: `SELECT 1` succeeded;
- application migration exited with code 0 at
  `m001_merge_cleanup_and_outbox`;
- API `/readyz`: HTTP 200;
- frontend `/`: HTTP 200;
- API and frontend runtime UID: `1001`;
- email/password sign-up is disabled in versioned `supabase/config.toml`.

## Security and operational boundary

- `.env.service-dev` is Git-ignored; no local endpoint credentials are committed.
- The local Supabase CLI warns that its services bind to the Docker host and use
  development defaults. It is for local development only and must not be exposed
  publicly.
- The complete self-hosted Supabase distribution is not included in APE Compose;
  local development uses the CLI-managed stack instead.

## Remaining production OAuth gate

This walkthrough does not claim Supabase provider authentication is complete.
`BE-13` must make the backend validate Supabase identities and provision APE
users/workspaces; `FE-12` must add the provider-only UI flow. Google and Yandex
applications, secrets, canonical HTTPS URLs, redirect allow-list and live E2E
remain external production work.

## Sources

- [Supabase CLI local development](https://supabase.com/docs/guides/local-development/cli/getting-started)
- [Supabase self-hosting overview](https://supabase.com/docs/guides/self-hosting)
