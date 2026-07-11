import { jobsResponse } from "@/lib/jobs-server"

export async function GET(request: Request, { params }: { params: Promise<{ jobId: string }> }) {
  return jobsResponse(`/api/jobs/${encodeURIComponent((await params).jobId)}`, undefined, request.headers.get("cookie"))
}
