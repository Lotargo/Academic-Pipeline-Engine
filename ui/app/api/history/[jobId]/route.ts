import { jobsResponse } from "@/lib/jobs-server"

export async function GET(request: Request, { params }: { params: Promise<{ jobId: string }> }) {
  return jobsResponse(`/api/history/${encodeURIComponent((await params).jobId)}`, undefined, request.headers.get("cookie"))
}

export async function DELETE(request: Request, { params }: { params: Promise<{ jobId: string }> }) {
  return jobsResponse(`/api/history/${encodeURIComponent((await params).jobId)}`, { method: "DELETE" }, request.headers.get("cookie"))
}
