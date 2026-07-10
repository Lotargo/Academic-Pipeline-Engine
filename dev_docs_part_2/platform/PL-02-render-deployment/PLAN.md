# PL-02 — Render Deployment

## Goal

Развернуть stateless frontend/API/workers на Render с внешними managed dependencies.

## Scope

- Render services;
- environment variables;
- service networking;
- deploy configuration;
- healthchecks;
- migrations и one-off jobs;
- rollback procedure.

## Not included

- persistent disk как обязательный storage;
- разработка application features;
- обход provider limits.

## Depends on

- PL-01;
- production DB/storage/queue/secret adapters.

## Invariants

- deploy не уничтожает данные;
- credentials находятся в Render secrets или внешнем Vault/KMS;
- migrations не запускаются конкурентно несколькими instances;
- image-based и Git-based deployment имеют явный owner.

## Acceptance

- все services запускаются;
- internal/public networking настроен;
- migration и rollback проверены;
- redeploy сохраняет jobs, accounts и artifacts.
