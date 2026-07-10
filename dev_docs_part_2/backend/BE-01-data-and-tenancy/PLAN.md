# BE-01 — Data and Tenancy

## Goal

Создать многопользовательскую модель данных с обязательной привязкой прикладных сущностей к workspace.

## Scope

- users, sessions, roles;
- organizations и workspaces;
- membership и tenant boundaries;
- ownership для jobs, artifacts, credentials и usage;
- базовые правила удаления и блокировки.

## Not included

- ORM-реализация и миграции;
- HTTP auth flow;
- очередь задач;
- UI.

## Depends on

- local-first release gate.

## Current state

Текущее приложение предполагает одного локального пользователя и не имеет tenant isolation.

## Target state

Каждый пользователь получает personal workspace. Все прикладные записи содержат `workspace_id`; доступ разрешается только через membership и роль.

## Invariants

- frontend-проверка не заменяет backend authorization;
- admin role не выдаётся через публичную регистрацию;
- пользователь не видит данные чужого workspace;
- production source of truth — PostgreSQL.

## Acceptance

- схема сущностей согласована;
- ownership и deletion policy описаны;
- tenant boundary покрыта тестовыми сценариями;
- BE-02 может реализовать модели без дополнительных архитектурных решений.
