import { NextResponse } from "next/server"
import { callbackUrl, providerAuthAdapter, setStartCookies } from "@/lib/provider-auth-server"
import { isProviderId } from "@/lib/provider-auth"

export async function GET(request: Request, { params }: { params: Promise<{ provider: string }> }) {
  const { provider } = await params
  if (!isProviderId(provider)) return NextResponse.json({ detail: "Unknown identity provider" }, { status: 404 })
  const redirect = new URL(callbackUrl(request))
  redirect.searchParams.set("provider", provider)
  const result = await providerAuthAdapter().begin(provider, redirect.toString())
  return setStartCookies(NextResponse.redirect(result.redirectUrl), result)
}
