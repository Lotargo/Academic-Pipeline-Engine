import { adminResponse } from "@/lib/admin-server"

export async function GET(request: Request) {
  return adminResponse("/api/auth/admin/jobs", undefined, request.headers.get("cookie"))
}
