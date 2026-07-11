import { NextResponse } from "next/server"
import type { AuthAction, Credentials, SessionContext, TokenPair } from "@/lib/auth-contract"
import { publicAuthError } from "@/lib/auth-contract"

export const REFRESH_COOKIE = "ape_refresh"
export const ACCESS_COOKIE = "ape_access"

const backendUrl = () => process.env.BACKEND_API_URL || "http://127.0.0.1:8000"

export async function backendAuth(path: string, body: unknown) {
  return fetch(`${backendUrl()}/api/auth/${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  })
}

export function sessionResponse(tokens: TokenPair, status = 200, context?: SessionContext) {
  const response = NextResponse.json(context ? { authenticated: true, context } : { authenticated: true }, { status })
  const secure = process.env.NODE_ENV === "production"
  response.cookies.set(REFRESH_COOKIE, tokens.refresh_token, { httpOnly: true, secure, sameSite: "lax", path: "/", maxAge: 60 * 60 * 24 * 30 })
  response.cookies.set(ACCESS_COOKIE, tokens.access_token, { httpOnly: true, secure, sameSite: "lax", path: "/", maxAge: 60 * 15 })
  return response
}

export async function backendContext(accessToken: string) {
  return fetch(`${backendUrl()}/api/auth/context`, {
    headers: { authorization: `Bearer ${accessToken}` },
    cache: "no-store",
  })
}

export function clearSession(response: NextResponse) {
  response.cookies.set(REFRESH_COOKIE, "", { httpOnly: true, path: "/", maxAge: 0 })
  response.cookies.set(ACCESS_COOKIE, "", { httpOnly: true, path: "/", maxAge: 0 })
  return response
}

export async function credentialsHandler(action: AuthAction, request: Request) {
  let credentials: Credentials
  try { credentials = await request.json() } catch { return NextResponse.json(publicAuthError(action, 422), { status: 422 }) }
  try {
    const upstream = await backendAuth(action, credentials)
    if (!upstream.ok) return NextResponse.json(publicAuthError(action, upstream.status), { status: upstream.status })
    return sessionResponse(await upstream.json() as TokenPair, action === "register" ? 201 : 200)
  } catch {
    return NextResponse.json(publicAuthError(action, 503), { status: 503 })
  }
}
