# BE-02 — ORM and Migrations

## Goal

Внедрить PostgreSQL persistence через SQLAlchemy 2 и управляемые миграции Alembic.

## Scope

- ORM-модели;
- session/unit-of-work boundaries;
- repository interfaces;
- Alembic migrations;
- raw SQL для критических атомарных операций.

## Not included

- auth UI;
- RabbitMQ;
- object storage;
- provider routing.

## Depends on

- BE-01.

## Current state

История и registry используют SQLite и локальные JSON-файлы.

## Target state

PostgreSQL становится production source of truth, при этом SQLite adapter сохраняется для local-first режима и тестов.

## Invariants

- ORM-модели не являются API-схемами;
- одна request/task — одна session;
- миграции обратимы или имеют явный rollback plan;
- сложные locks и counters могут использовать SQLAlchemy Core/raw SQL.

## Acceptance

- базовые модели и repositories реализованы;
- миграции воспроизводимы на чистой БД;
- SQLite и PostgreSQL проходят общий contract-test набор;
- схема не требует ручного редактирования production БД.
