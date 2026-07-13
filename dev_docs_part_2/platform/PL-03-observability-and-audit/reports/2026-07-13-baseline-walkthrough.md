# PL-03 baseline walkthrough — 2026-07-13

## Scope

Закрыты задачи `PL-03-T001`--`PL-03-T008` baseline checkpoint. Это не
завершение композиции `PL-03`: задачи `T009`--`T011` остаются открытыми.

## Commit

- `76f9a32 feat(observability): add correlation and safe health baseline`

## Delivered

- Добавлены redacted structured observability events и JSON formatter;
- middleware принимает безопасный correlation ID или создаёт новый, передаёт
  его в request/job/audit context и не добавляет resource IDs в metric labels;
- добавлены безопасные `/healthz`, `/readyz` и Prometheus-compatible `/metrics`;
- audit metadata и security/admin events получают correlation ID;
- общая redaction не допускает credentials в telemetry;
- добавлена bounded in-process telemetry и конфигурируемая retention policy,
  включая удаление просроченных audit events;
- зафиксированы минимальные alert conditions в конфигурации.

## Verification

- `\.venv\Scripts\python.exe -m pytest tests/test_observability.py tests/jobs/test_job_api.py tests/auth/test_admin_bootstrap.py tests/secrets/test_credential_store.py`
  — `11 passed`.
- Browser verification не запускалась: она зарезервирована за пользователем
  согласно правилам рабочего плана.

## Follow-up

`PL-03-T009`--`T011` были завершены тем же днём: добавлены provider/worker
failure telemetry, Celery Beat retention schedule и admin-only audit/health
views. Финальный состав и verification зафиксированы в `walkthrough.md`.
