# FE-06 — Admin Panel

## Goal

Создать отдельную защищённую админку для управления пользователями, ресурсами и состоянием системы.

## Scope

- admin-only layout;
- users и roles;
- platform credentials metadata;
- providers/models/global limits;
- jobs/queues overview;
- audit и health views;
- admin invite actions.

## Not included

- backend authorization;
- показ plaintext secrets;
- payment management.

## Depends on

- BE-03;
- BE-04;
- BE-05;
- BE-06;
- BE-07;
- BE-08;
- BE-09;
- PL-03.

## Invariants

- route guard не заменяет admin API authorization;
- user secrets не показываются администратору;
- опасные действия подтверждаются и аудируются;
- admin UI отделён от user cabinet.

## Acceptance

- user/admin/resource views работают;
- privilege errors обрабатываются;
- destructive actions подтверждаются;
- основные admin flows покрыты e2e tests.
