# BE-09 — Global Resources and BYOK

## Goal

Распределять общие бесплатные AI/OCR ресурсы и переключаться на пользовательские ключи без paid-статусов.

## Scope

- global provider budgets;
- availability states;
- fair-use concurrency;
- BYOK fallback;
- usage events;
- exhaustion messages.

## Not included

- оплаты, подписки и привилегии;
- обход upstream limits;
- точный token balance для недокументированных квот.

## Depends on

- BE-05;
- BE-07;
- BE-08.

## Target state

Platform credentials используются best-effort. При исчерпании или недоступности пользователь может продолжить со своим ключом.

## Invariants

- пожертвования не влияют на лимиты;
- нет free/paid ролей;
- один пользователь не захватывает всю очередь;
- VM/fingerprint rotation не используется для обхода квот.

## Acceptance

- budget/health states реализованы;
- fair-use policy не требует ложного точного quota balance;
- BYOK fallback работает;
- usage и exhaustion scenarios покрыты тестами.
