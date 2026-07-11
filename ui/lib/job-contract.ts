export const jobStatuses = ["pending", "queued", "running", "succeeded", "failed", "cancelled"] as const
export type JobStatus = typeof jobStatuses[number]

export interface JobStage { name: string; status: string; progress: number }
export interface ContinuationSource { source_type?: string; topic?: string; instructions?: string; context: Record<string, string>; document_plan?: string; runtime_template?: Record<string, unknown>; runtime_prompt_manifest?: Record<string, unknown>; template_mode?: string; template_id?: string; intent_override?: string; metadata_id?: string; run_id?: string }
export interface EditorAttachment { filename: string; content: string; attachment_type: "passive_reference" | "continuation_source"; token_count: number }
export interface EditorOptions { academic_mode?: boolean; author?: string; continuation_source?: ContinuationSource; artifact_override?: string; web_search_enabled?: boolean; attachments?: EditorAttachment[] }
export interface JobCreate { kind: "pipeline"; topic: string; instructions?: string; editor_options?: EditorOptions }
export interface Job {
  id: string; kind: "pipeline"; topic: string; instructions?: string
  editor_options?: EditorOptions
  status: JobStatus; current_stage: string | null; progress: number
  active_attempt: number; cancel_requested_at: string | null
  error_code: string | null; error_message: string | null
  created_at: string; updated_at: string; stages: JobStage[]
}
export interface JobEvent { id: string; type: string; created_at: string; job: Job }
export const activeJob = (job: Job) => !["succeeded", "failed", "cancelled"].includes(job.status)
