import type { Metadata } from "next"
import { AuthForm } from "@/app/components/auth-form"
import { AuthShell } from "@/app/components/auth-shell"
export const metadata: Metadata = { title: "Регистрация — Academic PE" }
export default function RegisterPage() { return <AuthShell title="Создать аккаунт" description="Мы создадим личное рабочее пространство для ваших проектов."><AuthForm action="register"/></AuthShell> }
