# PL-02 — Render Deployment

## Goal

Развернуть stateless frontend/API/workers на Render с внешними managed dependencies.

## Status and temporary sandbox

`PL-02` сохраняет целью постоянный deployment target и остаётся незавершённой.
До выбора home server, VPS или другого постоянного provider разрешён ограниченный
public smoke в Red Hat Developer Sandbox / OpenShift. Он описан в
[`OPENSHIFT_SANDBOX_INTERIM.md`](OPENSHIFT_SANDBOX_INTERIM.md), не меняет
acceptance этой композиции и не использует OpenShift Dev Spaces как runtime.

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
- признание временного Sandbox deployment production-эквивалентом.

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
