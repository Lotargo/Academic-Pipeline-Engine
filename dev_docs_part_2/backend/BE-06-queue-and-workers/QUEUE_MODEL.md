# BE-06 queue and worker model

## Boundaries

`TaskDispatcher.publish(TaskMessage)` — broker boundary. Сообщение содержит
только `event_id`, `job_id` и workload; payload и credential IDs workers читают
из PostgreSQL. `LocalBackgroundDispatcher` сохраняет local-first выполнение.

Production adapter — Celery с RabbitMQ. Объявлены очереди `generation`, `export`,
`research`, `maintenance`; dispatcher задаёт queue/routing key явно.

## Transactional outbox

API вызывает `create_job_with_outbox` внутри своего UoW. Job и outbox event либо
commit вместе, либо вместе rollback. Publisher выбирает доступные записи через
`FOR UPDATE SKIP LOCKED`, ставит lease, публикует и отмечает `published_at`.

При ошибке broker event остаётся в БД, lock снимается, attempts увеличивается, а
следующая попытка получает exponential backoff (не более пяти минут). В
`last_error` сохраняется только тип ошибки, без exception text и secrets.

## Delivery semantics

Celery использует late ack, reject on worker loss, prefetch=1 и bounded retry.
Семантика at-least-once: crash между publish и DB mark может дать duplicate.
`worker_deliveries(event_id, consumer)` — unique idempotency receipt; handler и
receipt commit в одной DB transaction, поэтому повторная доставка не повторяет
durable side effects.
