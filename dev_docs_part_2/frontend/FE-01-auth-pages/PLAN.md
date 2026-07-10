# FE-01 — Auth Pages

## Goal

Создать простой публичный flow регистрации, входа и восстановления пользовательской сессии.

## Scope

- `/register` и `/login`;
- session restore;
- logout;
- ошибки и blocked-account states;
- redirect в пользовательский кабинет.

## Not included

- backend auth implementation;
- admin dashboard;
- provider keys;
- marketing landing redesign.

## Depends on

- BE-03.

## Invariants

- UI не считается границей авторизации;
- refresh token не хранится в доступном JavaScript storage;
- ошибки не раскрывают существование аккаунта без необходимости;
- admin role нельзя выбрать при регистрации.

## Acceptance

- основные auth flows работают;
- loading/error/expired-session states обработаны;
- accessibility и mobile layout проверены;
- frontend использует согласованный auth contract.
