import { createEditorJob } from "@/lib/job-client"
import type { EditorOptions, Job } from "@/lib/job-contract"

export type EditorRuntimeProfile = "local" | "service"
export type EditorInput = { topic: string; instructions: string; editorOptions?: EditorOptions }

export function editorRuntimeProfile(): EditorRuntimeProfile {
  return process.env.NEXT_PUBLIC_APE_RUNTIME_PROFILE?.toLowerCase() === "local" ? "local" : "service"
}

export async function startEditorRun(input: EditorInput): Promise<{ profile: "local" } | { profile: "service"; job: Job }> {
  if (editorRuntimeProfile() === "service") {
    return { profile: "service", job: await createEditorJob(input.topic, input.instructions, input.editorOptions) }
  }
  const options = input.editorOptions
  const response = await fetch("/api/run", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      topic: input.topic,
      instructions: input.instructions,
      academic_mode: options?.academic_mode,
      author: options?.author,
      continuation_source: options?.continuation_source,
      artifact_override: options?.artifact_override,
      web_search_enabled: options?.web_search_enabled,
      attachments: options?.attachments,
    }),
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as { detail?: unknown }
    throw new Error(typeof body.detail === "string" ? body.detail : "Не удалось запустить локальный pipeline.")
  }
  return { profile: "local" }
}
