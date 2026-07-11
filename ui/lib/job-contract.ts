export const jobStatuses = ["pending", "queued", "running", "succeeded", "failed", "cancelled"] as const
export type JobStatus = typeof jobStatuses[number]

export interface JobStage { name: string; status: string; progress: number }
export interface Job {
  id: string; kind: "pipeline"; topic: string; instructions?: string
  status: JobStatus; current_stage: string | null; progress: number
  active_attempt: number; cancel_requested_at: string | null
  error_code: string | null; error_message: string | null
  created_at: string; updated_at: string; stages: JobStage[]
}
export interface JobEvent { id: string; type: string; created_at: string; job: Job }
export const activeJob = (job: Job) => !["succeeded", "failed", "cancelled"].includes(job.status)
