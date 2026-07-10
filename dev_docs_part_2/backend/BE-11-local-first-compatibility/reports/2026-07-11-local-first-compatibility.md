# BE-11 Local-First Compatibility — Walkthrough

## Tasks

`BE-11-T001`–`BE-11-T007`.

## Result

- Добавлены явные `local` и `cloud` runtime profiles.
- Local выбирает SQLite, local storage, background dispatcher и local AES wrapper.
- Cloud выбирает PostgreSQL, object storage, Celery и KMS и fail-fast валидирует настройки.
- Domain boundaries остаются `UoW/repository`, `ArtifactStorage`, `TaskDispatcher` и `KeyWrapper`.
- Local mode не требует cloud services или их environment variables.
- Migration всегда создаёт внешний ZIP backup с SHA-256 manifest до import callback.
- Rollback проверяет checksum/path safety, восстанавливает через staging и не смешивает старые файлы.
- Процедура описана в `MIGRATION.md`.

## Tests

- Cross-adapter/runtime subset — 17 passed, 3 skipped.
- `poetry run pytest -q` — 542 passed, 3 skipped.
- `git diff --check` — passed.

## Deviations and issues

Нет. Три skipped — PostgreSQL-specific contract cases без настроенного test database.

## Next step

Backend Part 2 завершён; следующая доступная композиция — FE-01 Auth Pages.
