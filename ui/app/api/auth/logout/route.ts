import { cookies } from "next/headers"
import { NextResponse } from "next/server"
import { clearProviderAuthCookies, IDENTITY_ACCESS_COOKIE, providerAuthAdapter } from "@/lib/provider-auth-server"

export async function POST() {
  const accessToken = (await cookies()).get(IDENTITY_ACCESS_COOKIE)?.value
  if (accessToken) await providerAuthAdapter().signOut(accessToken)
  return clearProviderAuthCookies(NextResponse.json({ authenticated: false }))
}
