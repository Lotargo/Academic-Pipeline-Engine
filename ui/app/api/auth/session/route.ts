import { cookies } from "next/headers"
import { NextResponse } from "next/server"
import { backendAuth, backendContext, clearSession, REFRESH_COOKIE, sessionResponse } from "@/lib/auth-server"
import type { SessionContext, TokenPair } from "@/lib/auth-contract"

export async function GET() {
  const refreshToken = (await cookies()).get(REFRESH_COOKIE)?.value
  if (!refreshToken) return NextResponse.json({ authenticated: false, reason: "missing" }, { status: 401 })
  try {
    const upstream = await backendAuth("refresh", { refresh_token: refreshToken })
    if (upstream.ok) {
      const tokens = await upstream.json() as TokenPair
      const context = await backendContext(tokens.access_token)
      if (!context.ok) {
        if (context.status === 401 || context.status === 403) return clearSession(NextResponse.json({ authenticated: false, reason: "expired" }, { status: context.status }))
        return NextResponse.json({ authenticated: false, reason: "unavailable" }, { status: 503 })
      }
      return sessionResponse(tokens, 200, await context.json() as SessionContext)
    }
    const reason = upstream.status === 403 ? "blocked" : "expired"
    return clearSession(NextResponse.json({ authenticated: false, reason }, { status: upstream.status }))
  } catch {
    return NextResponse.json({ authenticated: false, reason: "unavailable" }, { status: 503 })
  }
}
