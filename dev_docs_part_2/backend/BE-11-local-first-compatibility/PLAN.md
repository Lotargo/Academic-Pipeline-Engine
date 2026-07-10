# BE-11 — Local-First Compatibility

## Goal

Сохранить рабочую локальную версию и обеспечить контролируемый переход к cloud adapters.

## Scope

- adapter boundaries;
- local configuration;
- SQLite/local storage/local dispatcher;
- compatibility tests;
- import/migration path;
- feature flags или runtime profile.

## Not included

- новый cloud функционал сам по себе;
- смена лицензии;
- production deployment.

## Depends on

- все backend-композиции, чьи adapters заменяют local-first поведение.

## Invariants

- local-first release остаётся неизменяемой исторической точкой;
- cloud code не размазывается по domain logic;
- local mode не требует Supabase, RabbitMQ или Vault;
- migration не уничтожает исходные данные без backup.

## Acceptance

- local profile запускается;
- cloud profile запускается;
- общие contract tests проходят для adapters;
- migration/rollback procedure документирована и проверена.
