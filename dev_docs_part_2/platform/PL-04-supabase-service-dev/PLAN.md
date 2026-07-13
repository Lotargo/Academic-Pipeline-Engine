# PL-04 — Supabase Service Development

## Goal

Сделать `service-dev` воспроизводимым Linux-first окружением: официальный
локальный Supabase CLI/Docker stack для Auth/Postgres/Storage и контейнеры APE,
которые одинаково запускаются из Docker Desktop и WSL2.

## Scope

- versioned `supabase/config.toml` без provider secrets;
- provider-only local Auth policy и точные localhost callback URLs;
- profile-specific env contract для API, database, storage и broker;
- scripts start/status/stop для PowerShell и POSIX/WSL;
- применяемые к application schema Alembic migrations и controlled seed path;
- health/smoke checks для Supabase и APE containers.

## Not included

- self-hosted production Supabase distribution;
- Supabase Cloud project, provider credentials и canonical production URLs;
- public deployment;
- изменение application feature logic за пределами adapter boundary.

## Depends on

- PL-01 frontend/API image foundation (`T001`, `T002`, `T005`, `T006`);
- BE-11.

## Invariants

- standalone `postgres` container не называется `service-dev`;
- Supabase CLI stack и APE Compose остаются раздельными operational units;
- конфигурация, миграции и scripts хранятся в Git, secrets — только в ignored
  env files;
- Linux bridge к CLI stack задан явно (`host.docker.internal` с host-gateway
  mapping либо shared external network);
- полный self-hosted Supabase не вендорится в application compose.

## Acceptance

- чистый checkout запускает локальный Supabase CLI stack в Docker;
- application containers получают явные service-dev endpoints и проходят
  liveness/readiness smoke;
- POSIX/WSL и PowerShell entry points документированы и проверены;
- provider-only policy не включает email/password sign-up;
- создан walkthrough с командами, outputs и известными external OAuth gates.
