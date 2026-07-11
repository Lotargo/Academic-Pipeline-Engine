import { jobsResponse } from "@/lib/jobs-server"

export async function POST(request: Request, { params }: { params: Promise<{ artifactId: string }> }) {
  return jobsResponse(`/api/artifacts/${encodeURIComponent((await params).artifactId)}/download`, { method: "POST" }, request.headers.get("cookie"))
}
