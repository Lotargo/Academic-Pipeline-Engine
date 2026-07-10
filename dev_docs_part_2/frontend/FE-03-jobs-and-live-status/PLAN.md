# FE-03 — Jobs and Live Status

## Goal

Дать пользователю создание задания, наблюдение за pipeline и управляемую отмену.

## Scope

- job creation form;
- queued/running/retrying/completed/failed states;
- stage и progress view;
- live events;
- cancellation;
- recovery после reload.

## Not included

- worker implementation;
- provider settings;
- artifact history.

## Depends on

- FE-02;
- BE-06;
- BE-07.

## Invariants

- UI не выдумывает progress или quota balance;
- события всегда привязаны к одному job;
- cancel state отличается от instant cancellation;
- reload не теряет идентификатор активной задачи.

## Acceptance

- job можно создать и открыть;
- все lifecycle states отображаются;
- live update имеет fallback polling/reconnect;
- cancel и reload scenarios покрыты tests.
