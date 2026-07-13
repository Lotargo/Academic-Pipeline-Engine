# Personal settings API contract

Все endpoints требуют Bearer access token. Backend сам получает current user и
его active workspace; `user_id` и `workspace_id` в body не принимаются.

## Profile and editor defaults

- `GET /api/settings/me` возвращает `profile`, `editor_defaults` и безопасную
  metadata текущего workspace.
- `PUT /api/settings/me` обновляет display name, language, theme и defaults
  только текущего user. `editor_defaults` принадлежат current user в current
  workspace, поэтому участник workspace не меняет defaults другого участника.

```ts
type PersonalSettingsSnapshot = {
  profile: { display_name: string | null; language: "ru" | "en"; theme: "light" | "dark" | "system" }
  editor_defaults: {
    academic_mode: boolean; web_search_enabled: boolean
    author?: string; artifact_override?: string
  }
  workspace: { id: string; name: string; role: "owner" | "member" }
}
```

Global local-first `/api/config`, agent prompts, platform secrets and quotas не
являются частью этого API и не должны быть доступны из service settings.
