# FE-05 — Provider Settings

## Goal

Дать пользователю понятный выбор провайдера и безопасное управление собственными API-ключами.

## Scope

- provider/model selection;
- add/replace/delete key;
- masked key metadata;
- validation states;
- platform/BYOK choice;
- global resource availability messages.

## Not included

- encryption internals;
- admin credential management;
- paid plans.

## Depends on

- FE-02;
- BE-05;
- BE-08;
- BE-09.

## Invariants

- сохранённый plaintext key никогда не возвращается в UI;
- пожертвования не связаны с provider access;
- unknown quota отображается как availability, а не число;
- delete/replace требуют явного действия пользователя.

## Acceptance

- credential lifecycle доступен без показа plaintext;
- provider capabilities объяснены;
- exhaustion/BYOK states понятны;
- security и error scenarios покрыты tests.
