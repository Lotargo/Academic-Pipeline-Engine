# BE-08 — Provider Routing

## Goal

Создать единый registry и routing layer для platform и user provider credentials.

## Scope

- provider definitions и models;
- capability flags;
- credential source selection;
- fallback policy;
- health-aware routing;
- OpenAI-compatible custom providers.

## Not included

- secret encryption internals;
- global budget accounting;
- frontend settings UI.

## Depends on

- BE-05;
- BE-07.

## Target state

Pipeline запрашивает capability, а router выбирает provider/model/credential source по явной политике.

## Invariants

- неизвестная квота не представляется точным остатком;
- пользователь может выбрать собственный ключ;
- недоступный provider не ломает весь pipeline без fallback;
- provider-specific детали не проникают в domain logic.

## Acceptance

- registry и capability model реализованы;
- routing и fallback детерминированы;
- health state учитывается;
- contract tests покрывают platform, BYOK и custom provider сценарии.
