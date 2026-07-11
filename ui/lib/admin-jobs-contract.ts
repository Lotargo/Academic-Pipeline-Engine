import { z } from "zod"

export const adminJobsSnapshot = z.object({
  jobs: z.array(z.object({ status: z.enum(["pending", "queued", "running", "succeeded", "failed", "cancelled"]), count: z.number().int().nonnegative() })),
  queues: z.array(z.object({ workload: z.string(), pending: z.number().int().nonnegative(), retrying: z.number().int().nonnegative() })),
  generated_at: z.string(),
})

export type AdminJobsSnapshot = z.infer<typeof adminJobsSnapshot>
