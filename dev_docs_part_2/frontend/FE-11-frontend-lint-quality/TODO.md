# FE-11 TODO

## Required context

- `PLAN.md`
- `ui/eslint.config.mjs`
- `ui/package.json`
- только файлы UI, выбранные для текущего пакета предупреждений

## Baseline (2026-07-11)

`npm run lint` проходит без errors и сообщает 159 warnings:

- 102 `@typescript-eslint/no-explicit-any`;
- 22 `@typescript-eslint/no-unused-vars`;
- 16 `react-hooks/set-state-in-effect`;
- 5 `react-hooks/exhaustive-deps`;
- 5 `react/no-unescaped-entities`;
- 4 `react-hooks/immutability`;
- 3 `@next/next/no-img-element`;
- по одному `@typescript-eslint/no-unused-expressions` и `react-hooks/purity`.

Это baseline технического долга, обнаруженный после создания локальной
конфигурации ESLint. Он не блокирует текущие feature-задачи и не требует
массового рефакторинга в одной сессии.

## Tasks

- [ ] `FE-11-T001` Сохранить машиночитаемый baseline lint и проверку отсутствия новых errors.
- [ ] `FE-11-T002` Устранить high-risk warnings hooks в компонентах, затрагиваемых текущими feature-задачами.
- [ ] `FE-11-T003` Заменить `any` на контрактные типы в выбранном связанном UI-пакете.
- [ ] `FE-11-T004` Исправить `exhaustive-deps`, immutability, purity и unused-code warnings по компонентам.
- [ ] `FE-11-T005` Выбрать и применить Next image strategy для оставшихся `<img>`.
- [ ] `FE-11-T006` По мере очистки поднять соответствующие rules с warning до error.
- [ ] `FE-11-T007` Создать walkthrough с динамикой baseline и оставшимся долгом.
