# PL-03 audit-retention schedule — 2026-07-13

## Contract

`register_audit_pruning_task()` регистрирует Celery task
`academic_pe.maintenance.prune_audit_events` и запись Celery Beat
`ape-prune-audit-events`. Период определяется
`config/observability.yaml: maintenance.audit_pruning_seconds`; дефолт — один
раз в 24 часа, минимальное допустимое значение — один час.

Task направляется в очередь `maintenance`, открывает собственную database
session, удаляет только `AuditEvent` старше `retention.audit_event_days`, затем
делает commit. Повторный запуск безопасен: после первого запуска более нет
подходящих записей.

## Service-profile bootstrap

Bootstrap service worker должен единожды вызвать
`register_audit_pruning_task(celery_app, session_factory, config.retention,
interval_seconds=config.maintenance.audit_pruning_seconds, ...)`, затем:

1. запустить worker, потребляющий очередь `maintenance`;
2. запустить ровно один экземпляр Celery Beat с тем же зарегистрированным app;
3. собирать redacted events `audit.retention.pruned` и
   `audit.retention.prune_failed`.

`local` profile не обязан запускать Celery Beat и не получает зависимость от
broker. Docker process matrix и deployment wiring остаются объёмом `PL-01` и
`PL-02`.
