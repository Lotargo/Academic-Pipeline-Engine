import { NextResponse } from "next/server"
import { clearSession } from "@/lib/auth-server"
import { providerBackend } from "@/lib/provider-server"

export async function POST(request: Request) {
  const upstream = await providerBackend(
    "/api/auth/admin-invites/activate",
    { method: "POST", headers: { "content-type": "application/json" }, body: await request.text() },
    request.headers.get("cookie"),
  )
  if (!upstream) return NextResponse.json({ detail: "Authentication required" }, { status: 401 })
  if (upstream.ok) return clearSession(new NextResponse(null, { status: 204 }))

  const body = await upstream.text()
  return new NextResponse(body, {
    status: upstream.status,
    headers: { "content-type": upstream.headers.get("content-type") || "application/json", "cache-control": "no-store" },
  })
}
