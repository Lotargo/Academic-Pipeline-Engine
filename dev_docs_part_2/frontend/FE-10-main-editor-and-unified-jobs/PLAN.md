# FE-10 — Main Editor and Unified Jobs

## Goal

Перевести главный редактор с legacy `/api/run` и глобального status на единый
workspace-scoped Job API. Кабинет остаётся быстрым default entry point, а
редактор — расширенным entry point для той же сущности job.

## Scope

- общий create-job adapter для editor и `/cabinet/jobs`;
- mapping расширенных параметров редактора в job request;
- переход main editor на job snapshot/events, cancel и history;
- deep link между editor, cabinet jobs и history;
- удаление UI-зависимости от legacy `current_run` для service profile.

## Not included

- удаление local-first `/api/run`;
- изменение pipeline domain logic;
- новые provider settings или workspace modes.

## Depends on

- FE-03;
- FE-04;
- BE-07;
- BE-10;
- BE-11.

## Invariants

- оба entry point создают `Job` в активном workspace, а не две разные модели;
- editor не передаёт `workspace_id` и не назначает progress;
- расширенные editor options не теряются при создании job;
- local profile продолжает использовать legacy adapter явно;
- service profile не читает или не изменяет глобальный `current_run`.

## Acceptance

- job из editor виден в cabinet и history того же workspace;
- job из cabinet открывается в editor по ID без потери статуса;
- cancel, SSE recovery и artifacts работают одинаково из обоих entry point;
- service integration и local-first regression tests проходят.
