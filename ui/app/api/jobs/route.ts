import { jobsResponse } from "@/lib/jobs-server"

export async function GET(request: Request) { return jobsResponse("/api/jobs?active=true", undefined, request.headers.get("cookie")) }
export async function POST(request: Request) {
  const body = await request.text()
  return jobsResponse("/api/jobs", { method: "POST", headers: { "content-type": "application/json" }, body }, request.headers.get("cookie"))
}
