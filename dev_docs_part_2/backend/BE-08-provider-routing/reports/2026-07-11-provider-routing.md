# BE-08 Provider Routing — Walkthrough

## Tasks

`BE-08-T001`–`BE-08-T007`.

## Result

- Добавлены отдельные `ProviderRegistry` и `ProviderAdapter` contracts.
- Capability, model metadata, credential source и health state оформлены как provider-neutral модели.
- `ProviderRouter` детерминированно выбирает provider/model и возвращает только credential reference.
- User BYOK выбирается раньше platform credential; обе категории можно запретить в request policy.
- Open circuit исключает provider и приводит к fallback; degraded state участвует в стабильной сортировке.
- Custom OpenAI-compatible endpoints регистрируются с base URL без embedded credentials, query и fragment.
- Неизвестная квота не моделируется числом и не выдаётся как точный остаток.

## Tests

- `poetry run pytest tests/providers/test_provider_routing.py -q` — 9 passed.
- `poetry run pytest -q` — 526 passed, 3 skipped.
- `git diff --check` — passed.

## Deviations and issues

Нет. Persisted platform resource policy и budget accounting остаются в BE-09.

## Next step

BE-09 Global Resources and BYOK может подключить database-backed credential/health lookups к этому router.
