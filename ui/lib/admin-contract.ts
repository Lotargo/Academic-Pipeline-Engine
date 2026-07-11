import { z } from "zod"

export const adminUserSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  role: z.enum(["user", "admin", "service"]),
  status: z.enum(["active", "blocked", "deleted"]),
  created_at: z.string(),
})

export type AdminUser = z.infer<typeof adminUserSchema>

export const adminUsers = (value: unknown): AdminUser[] => z.array(adminUserSchema).parse(value)
