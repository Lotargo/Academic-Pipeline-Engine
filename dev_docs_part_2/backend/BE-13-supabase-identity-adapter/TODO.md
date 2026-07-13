# BE-13 TODO

## Required context

- `PLAN.md`
- `../BE-01-data-and-tenancy/PLAN.md`
- `../BE-03-auth-and-rbac/PLAN.md`
- `../BE-11-local-first-compatibility/PLAN.md`
- `../../platform/PL-04-supabase-service-dev/PLAN.md`

## Tasks

- [x] `BE-13-T001` Зафиксировать claims/identity-link contract и profile boundary.
- [x] `BE-13-T002` Добавить mock external identity verifier и contract tests.
- [x] `BE-13-T003` Добавить Supabase JWT/JWKS verifier с safe key refresh.
- [x] `BE-13-T004` Реализовать idempotent user/workspace/identity provisioning.
- [x] `BE-13-T005` Переключить service auth dependencies на identity adapter.
- [x] `BE-13-T006` Добавить negative, RBAC и tenant-isolation tests.
- [x] `BE-13-T007` Создать walkthrough-отчёт с production OAuth gate.
