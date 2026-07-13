import { cookies } from "next/headers"
import { NextResponse } from "next/server"
import { backendContext } from "@/lib/auth-server"
import {
  clearProviderAuthCookies,
  IDENTITY_ACCESS_COOKIE,
  IDENTITY_REFRESH_COOKIE,
  providerAuthAdapter,
  setIdentityCookies,
} from "@/lib/provider-auth-server"
import type { SessionContext } from "@/lib/auth-contract"

export async function GET() {
  const jar = await cookies()
  let accessToken = jar.get(IDENTITY_ACCESS_COOKIE)?.value
  const refreshToken = jar.get(IDENTITY_REFRESH_COOKIE)?.value
  if (!accessToken) return NextResponse.json({ authenticated: false, reason: "missing" }, { status: 401 })
  try {
    let context = await backendContext(accessToken)
    if (!context.ok && context.status === 401 && refreshToken) {
      const tokens = await providerAuthAdapter().refresh(refreshToken)
      if (tokens) {
        accessToken = tokens.access_token
        context = await backendContext(accessToken)
        if (context.ok) return setIdentityCookies(NextResponse.json({ authenticated: true, context: await context.json() as SessionContext }), tokens)
      }
    }
    if (!context.ok) {
      const reason = context.status === 403 ? "blocked" : "expired"
      return clearProviderAuthCookies(NextResponse.json({ authenticated: false, reason }, { status: context.status === 503 ? 503 : context.status }))
    }
    return NextResponse.json({ authenticated: true, context: await context.json() as SessionContext })
  } catch {
    return NextResponse.json({ authenticated: false, reason: "unavailable" }, { status: 503 })
  }
}
