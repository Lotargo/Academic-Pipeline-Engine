# BE-06 Queue and Workers walkthrough

- Дата и исполнитель: 2026-07-11, Codex.
- Композиция: BE-06 Queue and Workers.
- Задачи: BE-06-T001 — BE-06-T008.
- Commit/PR: текущий commit.

## Сделано

Добавлены TaskDispatcher interface, local-first adapter и Celery/RabbitMQ
adapter. Workloads разделены на generation, export, research и maintenance с
явным routing. Worker task использует late ack, reject-on-loss и bounded retry.

Job и outbox event создаются в одной транзакции. Publisher использует locking
lease, skip-locked batch claim и exponential retry при недоступности broker.
Сообщение содержит только IDs и workload. Worker delivery receipts обеспечивают
idempotent durable side effects при at-least-once delivery.

## Проверки

- Atomic job/outbox rollback и message minimization tests.
- Broker outage/retry, duplicate publish и worker redelivery tests.
- Queue routing, acknowledgement policy и local dispatcher tests.
- Полный `pytest -q`.
- Alembic SQLite upgrade/downgrade, `compileall`, `git diff --check`.

## Отклонения и известные проблемы

RabbitMQ integration test не запускается локально без broker; transport contract
проверен через dispatcher boundary и Celery configuration. Deployment wiring и
health checks относятся к PL-01/PL-02.

## Следующий шаг

Перейти к BE-08 Provider Routing.
