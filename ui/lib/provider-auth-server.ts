import { createHash, randomBytes } from "node:crypto"
import { NextResponse } from "next/server"
import { type CallbackStatus, type ProviderAuthMode, type ProviderId, publicProviderAuthMode } from "@/lib/provider-auth"

export const IDENTITY_ACCESS_COOKIE = "ape_identity_access"
export const IDENTITY_REFRESH_COOKIE = "ape_identity_refresh"
const PKCE_VERIFIER_COOKIE = "ape_oauth_pkce"
const OAUTH_STATE_COOKIE = "ape_oauth_state"

interface IdentityTokens {
  access_token: string
  refresh_token?: string
  expires_in?: number
}

interface StartResult {
  redirectUrl: string
  state?: string
  verifier?: string
}

interface CompletionResult {
  status: CallbackStatus
  tokens?: IdentityTokens
}

interface ProviderAuthAdapter {
  readonly mode: ProviderAuthMode
  begin(provider: ProviderId, callbackUrl: string): Promise<StartResult>
  complete(provider: ProviderId, callback: URL, verifier?: string, expectedState?: string): Promise<CompletionResult>
  refresh(refreshToken: string): Promise<IdentityTokens | null>
  signOut(accessToken: string): Promise<void>
}

const secure = () => process.env.NODE_ENV === "production"

export function providerAuthMode(): ProviderAuthMode {
  const configured = process.env.APE_PROVIDER_AUTH_ADAPTER
  if (configured === "supabase") return "supabase"
  if (configured === "mock") return "mock"
  return publicProviderAuthMode()
}

export function mockEmailAccessToken(value: unknown): string | null {
  if (providerAuthMode() !== "mock" || typeof value !== "string") return null
  const email = value.trim().toLowerCase()
  const domain = email.slice(email.lastIndexOf("@") + 1)
  if (email.length > 320 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || /(^|\.)(arpa|invalid|local|localhost|onion|test)$/.test(domain)) return null
  return `mock:email:${email}`
}

function configuredSupabaseUrl(): string | null {
  const value = process.env.APE_SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL
  if (!value) return null
  try {
    return new URL(value).origin
  } catch {
    return null
  }
}

function configuredAppOrigin(): string | null {
  const value = process.env.APE_PUBLIC_APP_ORIGIN
  if (!value) return null
  try {
    const url = new URL(value)
    return url.protocol === "http:" || url.protocol === "https:" ? url.origin : null
  } catch {
    return null
  }
}

function requestOrigin(request: Request): string {
  const configured = configuredAppOrigin()
  if (configured) return configured

  const requestUrl = new URL(request.url)
  const forwardedProtocol = request.headers.get("x-forwarded-proto")?.split(",")[0]?.trim()
  const forwardedHost = request.headers.get("x-forwarded-host")?.split(",")[0]?.trim()
  const protocol = forwardedProtocol || requestUrl.protocol.replace(/:$/, "")
  const host = forwardedHost || request.headers.get("host") || requestUrl.host
  try {
    return new URL(`${protocol}://${host}`).origin
  } catch {
    return requestUrl.origin
  }
}

class MockProviderAuthAdapter implements ProviderAuthAdapter {
  readonly mode = "mock" as const

  async begin(provider: ProviderId, callbackUrl: string): Promise<StartResult> {
    const callback = new URL(callbackUrl)
    callback.searchParams.set("mock_provider", provider)
    return { redirectUrl: callback.toString() }
  }

  async complete(provider: ProviderId, callback: URL): Promise<CompletionResult> {
    if (callback.searchParams.get("mock_provider") !== provider) return { status: "provider_error" }
    return { status: "complete", tokens: { access_token: `mock:${provider}`, expires_in: 60 * 60 } }
  }

  async refresh(): Promise<IdentityTokens | null> { return null }
  async signOut(): Promise<void> { /* Mock identity is server-cookie only. */ }
}

class SupabaseProviderAuthAdapter implements ProviderAuthAdapter {
  readonly mode = "supabase" as const

  private providerName(provider: ProviderId): string | null {
    if (provider === "google") return "google"
    // Yandex uses a Supabase custom OAuth/OIDC configuration.  The deployment
    // selects the concrete GoTrue provider alias; local mock mode never calls it.
    return process.env.APE_SUPABASE_YANDEX_PROVIDER_ID || null
  }

  async begin(provider: ProviderId, callbackUrl: string): Promise<StartResult> {
    const baseUrl = configuredSupabaseUrl()
    const upstreamProvider = this.providerName(provider)
    if (!baseUrl || !upstreamProvider) return { redirectUrl: callbackStateUrl(callbackUrl, "provider_error") }
    const verifier = randomBytes(48).toString("base64url")
    const state = randomBytes(32).toString("base64url")
    const challenge = createHash("sha256").update(verifier).digest("base64url")
    const authorize = new URL("/auth/v1/authorize", baseUrl)
    authorize.searchParams.set("provider", upstreamProvider)
    authorize.searchParams.set("redirect_to", callbackUrl)
    authorize.searchParams.set("code_challenge", challenge)
    authorize.searchParams.set("code_challenge_method", "s256")
    authorize.searchParams.set("state", state)
    return { redirectUrl: authorize.toString(), state, verifier }
  }

  async complete(provider: ProviderId, callback: URL, verifier?: string, expectedState?: string): Promise<CompletionResult> {
    const providerError = callback.searchParams.get("error")
    if (providerError) {
      if (providerError === "cancelled") return { status: "cancelled" }
      const denied = providerError === "access_denied"
      return { status: denied ? "denied" : "provider_error" }
    }
    if (!verifier || !expectedState || callback.searchParams.get("state") !== expectedState) return { status: "provider_error" }
    const code = callback.searchParams.get("code")
    if (!code || !this.providerName(provider)) return { status: "provider_error" }
    const baseUrl = configuredSupabaseUrl()
    if (!baseUrl) return { status: "provider_error" }
    try {
      const response = await fetch(`${baseUrl}/auth/v1/token?grant_type=pkce`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ auth_code: code, code_verifier: verifier }),
        cache: "no-store",
      })
      if (!response.ok) return { status: "provider_error" }
      const tokens = await response.json() as IdentityTokens
      if (!tokens.access_token || !tokens.refresh_token) return { status: "provider_error" }
      return { status: "complete", tokens }
    } catch {
      return { status: "provider_error" }
    }
  }

  async refresh(refreshToken: string): Promise<IdentityTokens | null> {
    const baseUrl = configuredSupabaseUrl()
    if (!baseUrl) return null
    try {
      const response = await fetch(`${baseUrl}/auth/v1/token?grant_type=refresh_token`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
        cache: "no-store",
      })
      if (!response.ok) return null
      const tokens = await response.json() as IdentityTokens
      return tokens.access_token && tokens.refresh_token ? tokens : null
    } catch {
      return null
    }
  }

  async signOut(accessToken: string): Promise<void> {
    const baseUrl = configuredSupabaseUrl()
    if (!baseUrl) return
    try {
      await fetch(`${baseUrl}/auth/v1/logout`, {
        method: "POST",
        headers: { authorization: `Bearer ${accessToken}` },
        cache: "no-store",
      })
    } catch { /* Clearing the first-party cookie remains the logout boundary. */ }
  }
}

function callbackStateUrl(callbackUrl: string, status: CallbackStatus): string {
  const callback = new URL("/auth/callback", callbackUrl)
  callback.searchParams.set("status", status)
  return callback.toString()
}

export function providerAuthAdapter(): ProviderAuthAdapter {
  return providerAuthMode() === "supabase" ? new SupabaseProviderAuthAdapter() : new MockProviderAuthAdapter()
}

export function callbackUrl(request: Request): string {
  return appUrl(request, "/api/auth/callback")
}

export function appUrl(request: Request, path: string): string {
  return new URL(path, requestOrigin(request)).toString()
}

export function setStartCookies(response: NextResponse, result: StartResult): NextResponse {
  if (result.verifier && result.state) {
    const options = { httpOnly: true, secure: secure(), sameSite: "lax" as const, path: "/", maxAge: 10 * 60 }
    response.cookies.set(PKCE_VERIFIER_COOKIE, result.verifier, options)
    response.cookies.set(OAUTH_STATE_COOKIE, result.state, options)
  }
  return response
}

export function setIdentityCookies(response: NextResponse, tokens: IdentityTokens): NextResponse {
  const options = { httpOnly: true, secure: secure(), sameSite: "lax" as const, path: "/" }
  response.cookies.set(IDENTITY_ACCESS_COOKIE, tokens.access_token, { ...options, maxAge: tokens.expires_in || 60 * 60 })
  if (tokens.refresh_token) response.cookies.set(IDENTITY_REFRESH_COOKIE, tokens.refresh_token, { ...options, maxAge: 60 * 60 * 24 * 30 })
  return response
}

export function clearProviderAuthCookies(response: NextResponse): NextResponse {
  const options = { httpOnly: true, secure: secure(), sameSite: "lax" as const, path: "/", maxAge: 0 }
  response.cookies.set(IDENTITY_ACCESS_COOKIE, "", options)
  response.cookies.set(IDENTITY_REFRESH_COOKIE, "", options)
  response.cookies.set(PKCE_VERIFIER_COOKIE, "", options)
  response.cookies.set(OAUTH_STATE_COOKIE, "", options)
  return response
}

export function clearTemporaryProviderCookies(response: NextResponse): NextResponse {
  const options = { httpOnly: true, secure: secure(), sameSite: "lax" as const, path: "/", maxAge: 0 }
  response.cookies.set(PKCE_VERIFIER_COOKIE, "", options)
  response.cookies.set(OAUTH_STATE_COOKIE, "", options)
  return response
}
