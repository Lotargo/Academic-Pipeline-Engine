# BE-03 Authentication and RBAC walkthrough

- Дата и исполнитель: 2026-07-11, Codex.
- Композиция: BE-03 Authentication and RBAC.
- Задачи: BE-03-T001 — BE-03-T008.
- Commit/PR: текущий commit.

## Сделано

Добавлены Argon2 password hashing, access JWT, opaque refresh sessions с rotation
и revocation, а также массовая инвалидизация access tokens через token version.
Публичная регистрация атомарно создаёт user, personal organization/workspace и
owner membership; роль admin через неё получить нельзя.

Auth router предоставляет registration, login, refresh и logout. Переиспользуемые
FastAPI dependencies проверяют активного пользователя, глобальную admin-role и
активное membership конкретного workspace. Чужой tenant возвращает 404.
Service wiring включается только при наличии production database environment.

## Проверки

- Auth/security suite: registration/login/rotation/logout, password-at-rest,
  privilege escalation, cross-tenant access, blocked user и token version.
- Полный `pytest -q`.
- `compileall`, Alembic upgrade/downgrade и `git diff --check`.

## Отклонения и известные проблемы

Первый administrator намеренно не создаётся: это scope BE-04. Существующие до
миграции пользователи получают marker, который не является валидным password
hash, и должны пройти будущий password-reset/bootstrap flow.

## Следующий шаг

Перейти к BE-04 Admin Bootstrap: безопасно создать первого администратора и
добавить защищённые administrative endpoints.
