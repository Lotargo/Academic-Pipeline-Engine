export const PROVIDERS = ["google", "yandex"] as const

export type ProviderId = typeof PROVIDERS[number]
export type ProviderAuthMode = "mock" | "supabase"
export type CallbackStatus = "complete" | "cancelled" | "denied" | "provider_error"

export function isProviderId(value: string): value is ProviderId {
  return (PROVIDERS as readonly string[]).includes(value)
}

export function publicProviderAuthMode(): ProviderAuthMode {
  return process.env.NEXT_PUBLIC_APE_PROVIDER_AUTH_ADAPTER === "supabase" ? "supabase" : "mock"
}
