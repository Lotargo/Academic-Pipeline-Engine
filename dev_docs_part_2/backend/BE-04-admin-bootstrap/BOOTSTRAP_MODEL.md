# BE-04 bootstrap model

Форма bootstrap — one-off CLI: `python -m academic_pe.admin_bootstrap`. Она
использует production sync database URL и не создаёт постоянный endpoint выпуска
администраторов.

- `first-admin --email EMAIL` создаёт первого admin и personal workspace либо
  повышает существующего active user, если admin ещё нет. Пароль читается через
  скрытый terminal prompt; `--password` предназначен только для automation с
  защищённой передачей аргументов.
- `create-invite --creator-id UUID [--ttl-hours 24]` требует active admin и
  печатает plaintext token ровно один раз.
- В БД хранится только SHA-256 token digest, expiry и optional single-use fields.
- Активация выполняется вошедшим пользователем через
  `POST /api/auth/admin-invites/activate`; invite не является login credential.
- Успешный bootstrap, выпуск, активация и отклонённая активация пишутся в
  `audit_events`. Активация повышает token version, инвалидируя старые JWT.
