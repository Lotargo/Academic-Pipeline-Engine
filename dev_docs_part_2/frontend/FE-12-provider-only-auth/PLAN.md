# FE-12 — Provider-only Auth

## Goal

Заменить service UI password-flow на provider-only вход через заменяемый auth
adapter, сохранив local-first интерфейс и не заявляя готовность OAuth раньше
внешней проверки.

## Scope

- Google и Яндекс provider buttons;
- `/auth/callback`, loading, cancel, denied, provider-error и session-restore
  states;
- UI interface с mock и Supabase implementations;
- logout и protected-route behavior при внешней session;
- unit/contract tests на mock adapter.

## Not included

- provider client IDs/secrets;
- production redirect allow-list;
- реальный OAuth E2E до постоянного HTTPS URL;
- удаление legacy registration/login pages из local/legacy profile.

## Depends on

- BE-13;
- FE-02;
- FE-08;
- PL-04.

## Invariants

- UI не считает OAuth state доказательством авторизации: backend остаётся
  trust boundary;
- provider identities не объединяются по email в браузере;
- токены не пишутся в открытое JavaScript storage;
- mock mode визуально и в telemetry не маскируется под настоящий OAuth;
- local-first profile не получает обязательной зависимости от Supabase.

## Acceptance

- все callback и error states доступны и протестированы на mock adapter;
- restore/logout корректно обновляют защищённые маршруты;
- frontend использует единый provider-auth contract;
- реальная OAuth проверка явно остаётся открытым deployment gate;
- создан walkthrough.
