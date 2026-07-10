# BE-01 tenant model walkthrough

- Дата и исполнитель: 2026-07-11, Codex.
- Композиция: BE-01 Data and Tenancy.
- Задачи: BE-01-T001 — BE-01-T007.
- Commit/PR: текущий commit (`docs: complete BE-01 data and tenancy`).

## Сделано

Зафиксированы tenant boundary, минимальные сущности и их связи, разделение
platform actor role и workspace membership role, ownership прикладных записей,
правила блокировки/удаления и предотвращения orphan records. Подготовлена
реализационно-независимая матрица изоляционных сценариев для BE-02 и BE-03.

## Проверки

- Сверены все acceptance criteria из `PLAN.md`.
- Проверено наличие явного `workspace_id` у jobs, artifacts, credentials и
  usage events.
- Проверены отрицательные сценарии для user, admin и service actor.
- Документальная проверка ссылок и статусов TODO.

## Отклонения и известные проблемы

Отклонений от плана нет. Конкретные SQL-типы, ограничения, RLS и HTTP-коды
намеренно оставлены следующим композициям. Аудируемый support-elevation flow
потребует уточнения в BE-03.

## Следующий шаг

Перейти к BE-02: выбрать PostgreSQL-провайдера согласно документации
композиции и реализовать ORM-модели и миграции без изменения инвариантов BE-01.
