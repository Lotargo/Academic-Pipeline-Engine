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

## Baseline checkpoint (2026-07-13)

Выполнен безопасный foundation без подключения production alert delivery или
admin UI: redacted `ObservabilityEvent`/`AuditEventInput`, JSON formatter,
request correlation middleware, Prometheus-compatible in-process metrics,
`/healthz` и `/readyz`, сохранение correlation ID в job payload/event и audit
metadata, а также конфигурируемая retention policy. `healthz` намеренно не
раскрывает provider, DB URL или secrets; local-first runtime не зависит от
наличия database/metrics backend.

Композиция остаётся незавершённой: следующие пакеты должны добавить
provider/worker failure signals, scheduled audit pruning и защищённые
admin-facing audit/health views после завершения API-contract части.
