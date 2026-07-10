# FE-04 — History and Artifacts

## Goal

Показать историю jobs и безопасный доступ к uploads и экспортированным документам.

## Scope

- history list и filters;
- job details;
- artifacts и upload metadata;
- signed download actions;
- archive/delete confirmation;
- empty и expired-link states.

## Not included

- object storage implementation;
- export generation;
- admin audit views.

## Depends on

- FE-02;
- BE-07;
- BE-10.

## Invariants

- storage keys не используются как публичные URLs;
- чужие artifact IDs не раскрывают данные;
- destructive actions требуют подтверждения;
- UI корректно обрабатывает удалённый или недоступный файл.

## Acceptance

- пользователь видит только свой workspace history;
- signed download flow работает;
- archive/delete и expired URL scenarios покрыты tests;
- large history не требует загрузки всех записей сразу.
