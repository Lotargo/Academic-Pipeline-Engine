import { z } from "zod"

const budget = z.union([
  z.object({ kind: z.literal("known"), limit: z.string(), used: z.string() }),
  z.object({ kind: z.literal("unknown") }),
])

export const adminResourceSnapshot = z.object({
  providers: z.array(z.object({
    id: z.string(), display_name: z.string(),
    models: z.array(z.object({ id: z.string(), capabilities: z.array(z.string()) })),
    health: z.enum(["healthy", "degraded", "open", "unknown"]),
    availability: z.enum(["available", "degraded", "exhausted", "unavailable"]),
    supports_byok: z.boolean(), platform_credential: z.null(), budget,
  })),
  fair_use: z.object({ max_active_per_user: z.number().int().nonnegative(), max_queued_per_user: z.number().int().nonnegative() }),
  generated_at: z.string(),
})

export type AdminResourceSnapshot = z.infer<typeof adminResourceSnapshot>
