import { jobsResponse } from "@/lib/jobs-server"

export async function GET(request: Request) {
  const query = new URL(request.url).search
  return jobsResponse(`/api/history${query}`, undefined, request.headers.get("cookie"))
}
