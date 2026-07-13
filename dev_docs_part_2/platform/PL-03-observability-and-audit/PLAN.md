# PL-03 — Observability and Audit

## Goal

Сделать ошибки, jobs, provider health и административные действия наблюдаемыми без утечки чувствительных данных.

## Scope

- structured logs;
- correlation IDs;
- metrics и health endpoints;
- worker/job monitoring;
- audit events;
- retention и redaction;
- alert thresholds.

## Not included

- хранение plaintext prompts/keys в telemetry;
- полноценная data analytics platform;
- frontend admin implementation.

## Depends on

- BE-03;
- BE-05;
- BE-06;
- BE-07;
- BE-08.

## Invariants

- API keys и auth secrets редактируются;
- audit log отделён от обычного debug log;
- job correlation сохраняется между API, broker и worker;
- health endpoint не раскрывает конфигурацию.

## Acceptance

- job можно проследить по correlation ID;
- provider/worker failures видимы;
- admin actions аудируются;
- redaction и retention tests проходят.

## Completion (2026-07-13)

Выполнен безопасный foundation без подключения production alert delivery или
admin UI: redacted `ObservabilityEvent`/`AuditEventInput`, JSON formatter,
request correlation middleware, Prometheus-compatible in-process metrics,
`/healthz` и `/readyz`, сохранение correlation ID в job payload/event и audit
metadata, а также конфигурируемая retention policy. `healthz` намеренно не
раскрывает provider, DB URL или secrets; local-first runtime не зависит от
наличия database/metrics backend.

Завершены последующие service-пакеты: provider routing фиксирует circuit-open
fallback и no-route failures, worker восстанавливает correlation ID из
persisted job payload и пишет redacted failure events, а безопасные агрегаты
попадают в process-local metrics. Celery Beat запускает idempotent audit
pruning в очереди `maintenance`; эксплуатационный контракт описан в
`reports/2026-07-13-retention-schedule.md`. Admin-only API предоставляет
metadata-free audit page и aggregate health snapshot, а обращения к этим views
сами аудируются.

Production alert delivery, dashboards и frontend admin implementation остаются
вне scope этой композиции. Полный итог — `reports/walkthrough.md`.
