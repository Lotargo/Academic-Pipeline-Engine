import type { Metadata } from "next"
import { AuthForm } from "@/app/components/auth-form"
import { AuthShell } from "@/app/components/auth-shell"
export const metadata: Metadata = { title: "Вход — Academic PE" }
export default async function LoginPage({ searchParams }: { searchParams: Promise<{ reason?: string }> }) { const { reason } = await searchParams; return <AuthShell title="С возвращением" description="Войдите, чтобы продолжить работу с документами."><AuthForm action="login" initialReason={reason}/></AuthShell> }
