# BE-04 — Admin Bootstrap

## Goal

Создать отдельный безопасный механизм выпуска первого администратора и одноразовых admin invites.

## Scope

- CLI, one-off job или временный bootstrap service;
- invite token generation;
- хранение только token hash;
- expiry, single use и audit;
- назначение admin role после активации.

## Not included

- постоянный публичный endpoint выдачи админов;
- отдельная auth-система;
- выпуск session JWT.

## Depends on

- BE-02;
- BE-03.

## Invariants

- invite не заменяет обычный login;
- plaintext invite не хранится в БД;
- использованный или просроченный invite не принимается;
- bootstrap surface не работает постоянно без необходимости.

## Acceptance

- первый admin создаётся воспроизводимо;
- новые admin invites одноразовые;
- все операции аудируются;
- повторное использование и privilege escalation покрыты тестами.
