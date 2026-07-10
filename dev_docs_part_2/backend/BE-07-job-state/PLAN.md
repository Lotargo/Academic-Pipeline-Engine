# BE-07 — Job State

## Goal

Перенести состояние pipeline из глобального `current_run` в устойчивую модель jobs, events и checkpoints.

## Scope

- job lifecycle;
- stages, attempts и events;
- cancellation;
- heartbeat;
- interrupted recovery;
- section checkpoints.

## Not included

- broker implementation;
- frontend live view;
- provider quota policy.

## Depends on

- BE-01;
- BE-02.

## Target state

PostgreSQL хранит status, stage, progress и checkpoint. Worker может безопасно продолжить или пометить оборванную задачу.

## Invariants

- `current_run` не source of truth;
- переходы статусов валидируются;
- отмена и retry идемпотентны;
- progress принадлежит конкретному job и workspace.

## Acceptance

- state machine формализована;
- checkpoints сохраняются после значимых этапов;
- зависшие jobs обнаруживаются;
- lifecycle и recovery tests проходят.
