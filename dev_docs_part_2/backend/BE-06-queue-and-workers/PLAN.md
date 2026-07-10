# BE-06 — Queue and Workers

## Goal

Заменить FastAPI BackgroundTasks на надёжную очередь длительных задач и отдельные workers.

## Scope

- RabbitMQ;
- Celery;
- TaskDispatcher interface;
- transactional outbox;
- queue routing;
- retries, acknowledgements и idempotency.

## Not included

- job lifecycle schema;
- provider routing;
- UI прогресса.

## Depends on

- BE-02;
- BE-07.

## Target state

API создаёт job и outbox event в одной транзакции. Dispatcher публикует `job_id`; workers загружают остальное из БД.

## Invariants

- queue не является source of truth;
- plaintext credentials не передаются в broker;
- повторная доставка не создаёт двойные результаты;
- local dispatcher сохраняется для local-first режима.

## Acceptance

- API и workers разделены;
- outbox переживает временную недоступность RabbitMQ;
- retry/idempotency tests проходят;
- отдельные очереди generation, export, research и maintenance работают.
