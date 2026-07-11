import { cookies } from "next/headers"
import { NextResponse } from "next/server"
import { backendAuth, clearSession, REFRESH_COOKIE } from "@/lib/auth-server"

export async function POST() {
  const refreshToken = (await cookies()).get(REFRESH_COOKIE)?.value
  if (refreshToken) { try { await backendAuth("logout", { refresh_token: refreshToken }) } catch { /* local logout still succeeds */ } }
  return clearSession(NextResponse.json({ authenticated: false }))
}
