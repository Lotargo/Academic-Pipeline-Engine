# BE-12 — Workspace Data Deletion

## Goal

Заменить legacy global reset на безопасное удаление данных одного workspace.

## Scope

- tenant-scoped API удаления пользовательских работ, metadata и artifacts;
- проверка active membership и owner role;
- удаление object-storage объектов только в namespace выбранного workspace;
- audit event, confirmation token и idempotent completion state;
- явное разделение `local` и `service` поведения.

## Not included

- удаление аккаунта или organization;
- admin-wide purge;
- UI настроек;
- изменение retention policy для system logs.

## Depends on

- BE-01;
- BE-02;
- BE-03;
- BE-10;
- BE-11.

## Invariants

- service API никогда не вызывает legacy global database reset;
- user может удалить только записи и storage objects своего active workspace;
- `workspace_id` берётся из защищённого server-side route parameter и проверяется
  через membership, а не принимается как доверенное client-side значение;
- cross-workspace request возвращает indistinguishable not-found response;
- удаление подтверждается явно, аудируется и не затрагивает чужие jobs, artifacts,
  credentials, usage или history;
- local hard reset остаётся отдельной local-first операцией и не доступен service UI.

## Acceptance

- контракт удаления и confirmation flow зафиксированы;
- tenant-isolation tests покрывают попытки удалить чужой workspace;
- storage cleanup ограничен workspace prefix;
- retry безопасен и не оставляет неконсистентный UI state.
