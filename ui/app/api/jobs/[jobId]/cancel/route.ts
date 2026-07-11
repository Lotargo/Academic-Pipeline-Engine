import { jobsResponse } from "@/lib/jobs-server"

export async function POST(request: Request, { params }: { params: Promise<{ jobId: string }> }) {
  return jobsResponse(`/api/jobs/${encodeURIComponent((await params).jobId)}/cancel`, { method: "POST" }, request.headers.get("cookie"))
}
