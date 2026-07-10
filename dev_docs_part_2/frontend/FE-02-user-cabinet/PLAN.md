# FE-02 — User Cabinet

## Goal

Создать основной shell личного кабинета и навигацию по workspace пользователя.

## Scope

- protected layout;
- profile и workspace context;
- navigation;
- provider/resource summary;
- responsive states;
- общие empty/error/loading views.

## Not included

- job editor;
- history details;
- admin panel;
- backend tenancy.

## Depends on

- FE-01;
- BE-01;
- BE-03.

## Invariants

- workspace context не подменяет backend membership check;
- кабинет не показывает данные до подтверждения session;
- shared UI не должен зависеть от admin-only данных.

## Acceptance

- protected shell работает;
- workspace context стабилен при navigation/reload;
- основные состояния покрыты tests;
- остальные FE-композиции могут подключаться без переписывания layout.
