# BE-04 Admin Bootstrap walkthrough

- Дата и исполнитель: 2026-07-11, Codex.
- Композиция: BE-04 Admin Bootstrap.
- Задачи: BE-04-T001 — BE-04-T007.
- Commit/PR: текущий commit.

## Сделано

Добавлен one-off CLI для воспроизводимого создания первого администратора и
выпуска одноразовых invites действующим admin. Пароль по умолчанию читается
скрытым prompt. Invite token генерируется CSPRNG, показывается один раз, а в БД
хранится только SHA-256 digest.

Аутентифицированный active user может активировать invite. Проверяются expiry и
single use; повышение роли увеличивает token version. Bootstrap, выпуск,
успешная активация и отклонения записываются в отдельный audit log.

## Проверки

- Security tests: exclusive/idempotent first admin, issuer authorization,
  hash-at-rest, expiry, single use, audit и token invalidation.
- Полный `pytest -q`.
- Alembic SQLite upgrade/downgrade, `compileall`, `git diff --check`.

## Отклонения и известные проблемы

CLI — намеренно операционная поверхность и не включается в HTTP server.
Централизованная observability/retention audit events относится к PL-03.

## Следующий шаг

Перейти к BE-05 Secret Storage.
