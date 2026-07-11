import type { EditorOptions, Job, JobCreate } from "@/lib/job-contract"

export async function jobRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, headers: { "content-type": "application/json", ...init?.headers }, cache: "no-store" })
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as { detail?: unknown }
    throw new Error(typeof body.detail === "string" ? body.detail : "Сервис jobs временно недоступен.")
  }
  return response.json() as Promise<T>
}

export function createEditorJob(topic: string, instructions: string, editorOptions?: EditorOptions) {
  const payload: JobCreate = { kind: "pipeline", topic: topic.trim(), instructions: instructions.trim() || undefined, editor_options: editorOptions }
  return jobRequest<Job>("/api/jobs", { method: "POST", body: JSON.stringify(payload) })
}
