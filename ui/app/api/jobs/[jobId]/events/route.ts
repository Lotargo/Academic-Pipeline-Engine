import { jobsBackend } from "@/lib/jobs-server"

export async function GET(request: Request, { params }: { params: Promise<{ jobId: string }> }) {
  const headers = new Headers({ accept: "text/event-stream" })
  const lastEventId = request.headers.get("last-event-id") || new URL(request.url).searchParams.get("last_event_id")
  if (lastEventId) headers.set("last-event-id", lastEventId)
  const resume = lastEventId ? `?last_event_id=${encodeURIComponent(lastEventId)}` : ""
  const upstream = await jobsBackend(`/api/jobs/${encodeURIComponent((await params).jobId)}/events${resume}`, { headers }, request.headers.get("cookie"))
  if (!upstream) return new Response("Unauthorized", { status: 401 })
  return new Response(upstream.body, { status: upstream.status, headers: { "content-type": upstream.headers.get("content-type") || "text/event-stream", "cache-control": "no-cache, no-transform", connection: "keep-alive" } })
}
