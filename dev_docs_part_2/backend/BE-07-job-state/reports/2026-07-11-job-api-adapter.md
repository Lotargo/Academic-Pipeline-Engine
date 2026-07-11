# BE-07 walkthrough — HTTP Job API adapter

## Причина доработки

После FE-03 обнаружен блокирующий разрыв: BE-07 содержал persistence/lifecycle,
но не предоставлял HTTP API и SSE, требуемые frontend-композицией. Поэтому
BE-07 временно возвращалась в индекс как незавершённая.

## Task

Закрыт `BE-07-T009`.

## Сделано

- `POST/GET /api/jobs`, `GET /api/jobs/{id}`, cancellation и SSE endpoint.
- Workspace выбирается backend по active membership текущего principal; client
  не передаёт workspace ID. Foreign job returns 404.
- Создание вызывает `create_job_with_outbox`, то есть job и outbox event пишутся
  в одной транзакции. Cancel остаётся request-only и идемпотентным.
- Next legacy rewrite исключает `/api/jobs`, чтобы route handlers передавали
  httpOnly access cookie как Bearer token, включая nested cancel/SSE routes.

## Проверки

- `pytest tests/jobs/test_job_api.py tests/jobs/test_lifecycle.py -q` — passed.
- `node --test ui/tests/jobs-api.mjs` — passed against local service-dev setup.

## Отклонения

SSE публикует только persisted `job_events`; worker обязан добавлять lifecycle
events через `JobLifecycleRepository`, как и предусмотрено BE-07.
