import { adminResponse } from "@/lib/admin-server"

export async function GET(request: Request) {
  const query = new URL(request.url).search
  return adminResponse(`/api/auth/admin/audit-events${query}`, undefined, request.headers.get("cookie"))
}
