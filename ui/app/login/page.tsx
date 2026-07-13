import type { Metadata } from "next"
import { AuthForm } from "@/app/components/auth-form"
import { AuthShell } from "@/app/components/auth-shell"
import { ProviderAuthChooser } from "@/app/components/provider-auth-chooser"
import { publicProviderAuthMode } from "@/lib/provider-auth"
export const metadata: Metadata = { title: "Вход — Academic PE" }
export default async function LoginPage({ searchParams }: { searchParams: Promise<{ reason?: string }> }) {
  const { reason } = await searchParams
  if (process.env.NEXT_PUBLIC_APE_RUNTIME_PROFILE === "local") return <AuthShell title="С возвращением" description="Войдите, чтобы продолжить работу с документами."><AuthForm action="login" initialReason={reason}/></AuthShell>
  return <AuthShell title="Вход в Academic PE" description="Выберите провайдера для безопасного входа."><ProviderAuthChooser mode={publicProviderAuthMode()} /></AuthShell>
}
