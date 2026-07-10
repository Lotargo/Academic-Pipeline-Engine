# BE-09 Global Resources and BYOK — Walkthrough

## Tasks

`BE-09-T001`–`BE-09-T007`.

## Result

- Определены known/unknown budget и available/degraded/exhausted/unavailable states.
- Known budget поддерживает reservation, settle и release; unknown budget работает best-effort без ложного остатка.
- Usage recorder сохраняет фактические provider metrics через существующий `UsageEvent`.
- Fair-use coordinator ограничивает active и queued jobs отдельно для каждого пользователя.
- Routing получил явные user-first, platform-first, user-only и platform-only credential policies.
- Обычный сервисный путь использует platform-first, явный BYOK — user-only.
- Exhaustion возвращает стабильный code и безопасное сообщение о возможности BYOK; recovery явный.
- Платные роли, donation privileges и механизмы обхода upstream limits отсутствуют.

## Tests

- `poetry run pytest tests/providers -q` — 15 passed.
- `poetry run pytest -q` — 532 passed, 3 skipped.
- `git diff --check` — passed.

## Deviations and issues

Нет. Coordinator является policy/reference implementation; production может внедрить shared transactional adapter через тот же boundary без изменения routing contract.

## Next step

BE-10 Object Storage.
