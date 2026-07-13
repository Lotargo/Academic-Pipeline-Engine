import { adminResponse } from "@/lib/admin-server"

export async function GET(request: Request) {
  return adminResponse("/api/auth/admin/health", undefined, request.headers.get("cookie"))
}
