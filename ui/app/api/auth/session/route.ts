import { cookies } from "next/headers"
import { NextResponse } from "next/server"
import { backendAuth, clearSession, REFRESH_COOKIE, sessionResponse } from "@/lib/auth-server"
import type { TokenPair } from "@/lib/auth-contract"

export async function GET() {
  const refreshToken = (await cookies()).get(REFRESH_COOKIE)?.value
  if (!refreshToken) return NextResponse.json({ authenticated: false, reason: "missing" }, { status: 401 })
  try {
    const upstream = await backendAuth("refresh", { refresh_token: refreshToken })
    if (upstream.ok) return sessionResponse(await upstream.json() as TokenPair)
    const reason = upstream.status === 403 ? "blocked" : "expired"
    return clearSession(NextResponse.json({ authenticated: false, reason }, { status: upstream.status }))
  } catch {
    return NextResponse.json({ authenticated: false, reason: "unavailable" }, { status: 503 })
  }
}
