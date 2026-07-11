# BE-12 TODO

## Required context

- `PLAN.md`
- `../BE-01-data-and-tenancy/PLAN.md`
- `../BE-03-auth-and-rbac/AUTH_MODEL.md`
- `../BE-10-object-storage/PLAN.md`
- `../BE-11-local-first-compatibility/PLAN.md`

## Tasks

- [ ] `BE-12-T001` Зафиксировать delete/confirmation API contract и audit model.
- [ ] `BE-12-T002` Заменить service-доступ к legacy global reset на scoped service.
- [ ] `BE-12-T003` Реализовать tenant-scoped cleanup jobs, metadata и artifacts.
- [ ] `BE-12-T004` Реализовать object-storage cleanup по workspace prefix.
- [ ] `BE-12-T005` Добавить owner/membership, cross-tenant и retry tests.
- [ ] `BE-12-T006` Документировать различия local и service reset.
- [ ] `BE-12-T007` Создать walkthrough-отчёт.
