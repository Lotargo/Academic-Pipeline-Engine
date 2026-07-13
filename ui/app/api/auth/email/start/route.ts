import { NextResponse } from "next/server"
import { mockEmailAccessToken, providerAuthMode, setIdentityCookies } from "@/lib/provider-auth-server"

export async function POST(request: Request) {
  if (providerAuthMode() !== "mock") {
    return NextResponse.json({ detail: "Email sign-in is not configured" }, { status: 404 })
  }
  const body = await request.json().catch(() => null)
  const accessToken = mockEmailAccessToken(
    body && typeof body === "object" && "email" in body ? body.email : null,
  )
  if (!accessToken) {
    return NextResponse.json({ detail: "Введите корректный email" }, { status: 400 })
  }
  const response = NextResponse.json({ ok: true }, { headers: { "cache-control": "no-store" } })
  return setIdentityCookies(response, { access_token: accessToken, expires_in: 60 * 60 })
}
