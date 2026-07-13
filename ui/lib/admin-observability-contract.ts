import { z } from "zod"

const uuid = z.string().uuid()

export const adminAuditEvent = z.object({
  id: uuid,
  event_type: z.string().min(1).max(120),
  actor_user_id: uuid.nullable(),
  target_user_id: uuid.nullable(),
  correlation_id: z.string().min(8).max(128).nullable(),
  created_at: z.string(),
})

export const adminAuditPage = z.object({
  events: z.array(adminAuditEvent),
  limit: z.number().int().min(1).max(100),
  offset: z.number().int().nonnegative(),
  next_offset: z.number().int().nonnegative().nullable(),
})

export const adminHealthSnapshot = z.object({
  status: z.literal("ok"),
  generated_at: z.string(),
  telemetry: z.object({
    events_retained: z.number().int().nonnegative(),
    http_requests: z.number().int().nonnegative(),
    event_counts: z.array(z.object({
      event_type: z.string().min(1).max(120),
      severity: z.enum(["debug", "info", "warning", "error"]),
      outcome: z.string().min(1).max(40),
      count: z.number().int().nonnegative(),
    })),
  }),
})

export type AdminAuditPage = z.infer<typeof adminAuditPage>
export type AdminHealthSnapshot = z.infer<typeof adminHealthSnapshot>
