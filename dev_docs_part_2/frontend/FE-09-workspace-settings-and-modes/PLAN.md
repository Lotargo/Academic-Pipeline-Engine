# FE-09 — Workspace Settings and Modes

## Goal

Перенести user-facing настройки из legacy profile modal и agent settings в
личный кабинет, сохранив понятный простой режим и отдельный advanced режим.

## Scope

- раздел `Workspace settings` в cabinet navigation;
- профиль: display name, avatar, language и theme;
- простой режим с минимальными безопасными настройками;
- advanced режим с полным agent/document configuration;
- collapsed-by-default sections: template, layout/typography и AI pipeline;
- явный destructive action для «очистить мои работы» с понятным scope;
- ссылки на отдельные provider/BYOK settings из FE-05.

## Not included

- provider credential forms и plaintext keys;
- admin settings;
- global database reset;
- account deletion.

## Depends on

- FE-02;
- FE-05;
- BE-12.

## Invariants

- простой режим не скрывает необходимый user control, но не показывает сложные
  agent/template параметры без явного перехода в advanced;
- advanced режим сохраняет весь текущий набор настроек без потери значений;
- все три крупных configuration sections закрыты по умолчанию;
- destructive copy всегда говорит «только мои работы в этом workspace»;
- frontend не определяет scope удаления: workspace authorization остаётся backend responsibility;
- legacy local profile не смешивается неявно с service profile/workspace data.

## Acceptance

- профильные настройки доступны из cabinet и сохраняют существующую UX-функцию;
- basic и advanced flows понятны и имеют безопасный переход между режимами;
- accordion initial state и keyboard accessibility покрыты tests;
- cleanup подтверждает scope и не предлагает global reset;
- provider settings остаются отдельной безопасной границей FE-05.
