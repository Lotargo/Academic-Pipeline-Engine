# PL-03 walkthrough

## Scope

- Tasks: `PL-03-T001`--`PL-03-T011`
- Commit/PR: pending

## Delivered

- Added redacted structured observability/audit event schemas, request and job
  correlation, safe `/healthz`, `/readyz` and Prometheus-compatible metrics.
- Made correlation survive the broker boundary: workers reload it from the
  persisted job payload, never from a queue message.
- Recorded redacted worker-delivery failures and provider circuit-open/no-route
  routing signals; aggregate counters are available to safe metrics and the
  protected admin health view.
- Added an idempotent Celery Beat audit-pruning task on the `maintenance`
  queue, with a one-hour minimum interval and documented service bootstrap.
- Added admin-only audit and health endpoints. Audit reads return no raw
  metadata, while both views themselves create audit events.

## Verification

- Targeted contract regression: `35 passed`.
- Full check: `.venv\\Scripts\\python.exe -m pytest` — `673 passed, 3 skipped`.
- `git diff --check` is run before commit.
- Browser verification was not run, per the project rule.

## Deviations and next step

- No production alert-delivery provider or dashboard was introduced; both are
  outside the PL-03 scope.
- Docker process wiring for the maintenance worker and Celery Beat remains
  PL-01 work.
- `FE-06` can now consume the protected admin contracts; its visual verification
  remains user-owned.
