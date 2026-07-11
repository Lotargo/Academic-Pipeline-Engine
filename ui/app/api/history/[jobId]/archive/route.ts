import { jobsResponse } from "@/lib/jobs-server"

export async function POST(request: Request, { params }: { params: Promise<{ jobId: string }> }) {
  return jobsResponse(`/api/history/${encodeURIComponent((await params).jobId)}/archive`, { method: "POST" }, request.headers.get("cookie"))
}
