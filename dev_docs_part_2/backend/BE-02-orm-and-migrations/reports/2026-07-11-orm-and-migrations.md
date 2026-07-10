# BE-02 ORM and migrations walkthrough

- Дата и исполнитель: 2026-07-11, Codex.
- Композиция: BE-02 ORM and Migrations.
- Задачи: BE-02-T001 — BE-02-T008.
- Commit/PR: текущий commit (`feat: complete BE-02 persistence foundation`).

## Сделано

Зафиксированы async API и sync worker session boundaries. Добавлены SQLAlchemy
declarative base, конфигурация двух PostgreSQL engines/session factories,
tenant-модели BE-01, синхронные и асинхронные repository/UoW interfaces и
реализации. Настроен Alembic и создан обратимый baseline для девяти таблиц.

Repository contract проверяет tenant filtering, rollback и запрет
межтенантной связи artifact/job на SQLite и PostgreSQL. Старый
`SQLiteRegistryStore` не заменён и остаётся local-first адаптером.

## Проверки

- `pytest -q`: 501 passed (включая существующие SQLite registry tests).
- Contract suite с SQLite и PostgreSQL 16: 6 passed.
- Alembic PostgreSQL: upgrade, check, downgrade, повторный upgrade/downgrade.
- Alembic SQLite: upgrade, downgrade, upgrade, check.
- `compileall` для persistence и migrations.

## Отклонения и известные проблемы

Production-провайдер PostgreSQL не выбран: connection layer не зависит от
Supabase/Neon и принимает стандартные SQLAlchemy URLs. API/worker wiring,
аутентификация и outbox относятся к следующим композициям. Временный Docker
PostgreSQL использовался только для contract tests.

## Следующий шаг

Перейти к BE-03 Authentication and RBAC и подключить request-scoped async UoW
после определения auth flow.
