"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { FormEvent, useState } from "react"
import { AlertCircle, Eye, EyeOff, Loader2 } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import type { AuthAction, AuthErrorPayload } from "@/lib/auth-contract"

const restoreErrors: Record<string, AuthErrorPayload> = {
  expired: { code: "invalid_credentials", message: "Сессия истекла. Войдите снова." },
  blocked: { code: "account_blocked", message: "Аккаунт заблокирован. Обратитесь к администратору." },
  unavailable: { code: "service_unavailable", message: "Не удалось восстановить сессию. Войдите снова." },
}

export function AuthForm({ action, initialReason }: { action: AuthAction, initialReason?: string }) {
  const router = useRouter()
  const [pending, setPending] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<AuthErrorPayload | null>(initialReason ? restoreErrors[initialReason] ?? null : null)
  const isLogin = action === "login"

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setPending(true); setError(null)
    const data = new FormData(event.currentTarget)
    try {
      const response = await fetch(`/api/auth/${action}`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ email: data.get("email"), password: data.get("password") }) })
      if (!response.ok) { setError(await response.json()); return }
      router.replace("/cabinet"); router.refresh()
    } catch { setError({ code: "service_unavailable", message: "Нет связи с сервисом. Проверьте подключение и повторите попытку." }) }
    finally { setPending(false) }
  }

  return <form className="space-y-5" onSubmit={submit} noValidate>
    {error && <Alert variant="destructive"><AlertCircle aria-hidden="true"/><AlertTitle>{error.code === "account_blocked" ? "Доступ приостановлен" : "Не удалось продолжить"}</AlertTitle><AlertDescription>{error.message}</AlertDescription></Alert>}
    <div className="space-y-2"><Label htmlFor="email">Email</Label><Input id="email" name="email" type="email" inputMode="email" autoComplete="email" required disabled={pending} placeholder="name@example.com" /></div>
    <div className="space-y-2"><div className="flex items-center justify-between"><Label htmlFor="password">Пароль</Label>{isLogin && <span className="text-xs text-muted-foreground">Не менее 12 символов</span>}</div><div className="relative"><Input id="password" name="password" type={showPassword ? "text" : "password"} autoComplete={isLogin ? "current-password" : "new-password"} minLength={12} required disabled={pending} className="pr-11"/><button type="button" onClick={() => setShowPassword(value => !value)} className="absolute inset-y-0 right-0 grid w-11 place-items-center text-muted-foreground hover:text-foreground" aria-label={showPassword ? "Скрыть пароль" : "Показать пароль"}>{showPassword ? <EyeOff className="size-4"/> : <Eye className="size-4"/>}</button></div></div>
    <Button className="h-11 w-full" disabled={pending}>{pending && <Loader2 className="animate-spin"/>}{isLogin ? "Войти" : "Создать аккаунт"}</Button>
    <p className="text-center text-sm text-muted-foreground">{isLogin ? "Ещё нет аккаунта?" : "Уже зарегистрированы?"} <Link className="font-medium text-foreground underline-offset-4 hover:underline" href={isLogin ? "/register" : "/login"}>{isLogin ? "Регистрация" : "Войти"}</Link></p>
  </form>
}
