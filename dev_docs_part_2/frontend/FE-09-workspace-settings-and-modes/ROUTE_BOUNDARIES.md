# FE-09 route boundaries

## Service profile

- `GET/PUT /api/settings/me` — личный профиль текущего authenticated user и
  editor defaults этого user в его активном workspace. Клиент не передаёт
  `user_id` или `workspace_id`.
- `GET/PUT /api/provider-settings` и `/api/credentials/*` — личный выбор
  provider/model и только credentials, созданные текущим user в активном
  workspace. Они не являются server-wide configuration и не видны другим
  участникам workspace.
- Next.js BFF routes передают HTTP-only identity cookie как Bearer token; эти
  маршруты исключены из generic FastAPI rewrite.
- Полный agent/template configuration из local-first `ConfigEditor` не
  переносится: он изменяет global local config и поэтому запрещён в service UI.

## Local profile

Local-first продолжает использовать legacy `/api/config`, `/api/secrets` и
browser profile modal. Эти endpoints и localStorage не служат источником
service-настроек и не получают service identity cookies.

## Credential boundary

В `service-dev` допускается только явно включённый `local-aes` wrapper с
локальным generated key из `.env.service-dev`. Для production нужен отдельный
KMS/Vault adapter; без него credential create/replace/delete возвращают 503 и
plaintext не сохраняется.
