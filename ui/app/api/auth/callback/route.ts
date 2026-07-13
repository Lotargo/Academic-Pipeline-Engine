import { cookies } from "next/headers"
import { NextResponse } from "next/server"
import {
  clearTemporaryProviderCookies,
  appUrl,
  providerAuthAdapter,
  setIdentityCookies,
} from "@/lib/provider-auth-server"
import { isProviderId, type CallbackStatus } from "@/lib/provider-auth"

const callbackPage = (request: Request, status: CallbackStatus) => {
  const target = new URL(appUrl(request, "/auth/callback"))
  target.searchParams.set("status", status)
  return target
}

export async function GET(request: Request) {
  const callback = new URL(request.url)
  const provider = callback.searchParams.get("mock_provider") || callback.searchParams.get("provider") || "google"
  if (!isProviderId(provider)) return clearTemporaryProviderCookies(NextResponse.redirect(callbackPage(request, "provider_error")))
  const jar = await cookies()
  const result = await providerAuthAdapter().complete(
    provider,
    callback,
    jar.get("ape_oauth_pkce")?.value,
    jar.get("ape_oauth_state")?.value,
  )
  if (result.status !== "complete" || !result.tokens) {
    return clearTemporaryProviderCookies(NextResponse.redirect(callbackPage(request, result.status)))
  }
  return clearTemporaryProviderCookies(setIdentityCookies(NextResponse.redirect(callbackPage(request, "complete")), result.tokens))
}
