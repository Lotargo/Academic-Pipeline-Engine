import type { EditorOptions } from "@/lib/job-contract"

export type PersonalSettingsSnapshot = {
  profile: { display_name: string | null; language: "ru" | "en"; theme: "light" | "dark" | "system" }
  editor_defaults: Pick<EditorOptions, "academic_mode" | "web_search_enabled" | "author" | "artifact_override">
  workspace: { id: string; name: string; role: string }
}

const isRecord = (value: unknown): value is Record<string, unknown> => Boolean(value) && typeof value === "object" && !Array.isArray(value)
const text = (value: unknown): string | null => typeof value === "string" && value.trim() ? value : null

export function parsePersonalSettings(value: unknown): PersonalSettingsSnapshot | null {
  if (!isRecord(value) || !isRecord(value.profile) || !isRecord(value.editor_defaults) || !isRecord(value.workspace)) return null
  const language = value.profile.language === "en" ? "en" : value.profile.language === "ru" ? "ru" : null
  const theme = ["light", "dark", "system"].includes(String(value.profile.theme)) ? value.profile.theme as "light" | "dark" | "system" : null
  const workspaceId = text(value.workspace.id)
  const workspaceName = text(value.workspace.name)
  if (!language || !theme || !workspaceId || !workspaceName) return null
  return {
    profile: { display_name: text(value.profile.display_name), language, theme },
    editor_defaults: {
      academic_mode: Boolean(value.editor_defaults.academic_mode),
      web_search_enabled: Boolean(value.editor_defaults.web_search_enabled),
      author: text(value.editor_defaults.author) ?? undefined,
      artifact_override: text(value.editor_defaults.artifact_override) ?? undefined,
    },
    workspace: { id: workspaceId, name: workspaceName, role: text(value.workspace.role) ?? "member" },
  }
}
