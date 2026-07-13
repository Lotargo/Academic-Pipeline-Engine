import { AuthShell } from "@/app/components/auth-shell"
import { ProviderAuthCallback } from "@/app/components/provider-auth-callback"
import type { CallbackStatus } from "@/lib/provider-auth"

const statuses = new Set<CallbackStatus>(["complete", "cancelled", "denied", "provider_error"])

export default async function AuthCallbackPage({ searchParams }: { searchParams: Promise<{ status?: string }> }) {
  const { status: value } = await searchParams
  const status: CallbackStatus = value && statuses.has(value as CallbackStatus) ? value as CallbackStatus : "provider_error"
  return <AuthShell title="Вход через провайдера" description="Academic PE проверяет сессию на сервере."><ProviderAuthCallback status={status} /></AuthShell>
}
