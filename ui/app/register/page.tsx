import type { Metadata } from "next"
import { AuthForm } from "@/app/components/auth-form"
import { AuthShell } from "@/app/components/auth-shell"
import { redirect } from "next/navigation"
export const metadata: Metadata = { title: "Регистрация — Academic PE" }
export default function RegisterPage() {
  if (process.env.NEXT_PUBLIC_APE_RUNTIME_PROFILE !== "local") redirect("/login")
  return <AuthShell title="Создать аккаунт" description="Мы создадим личное рабочее пространство для ваших проектов."><AuthForm action="register"/></AuthShell>
}
