"use client"

import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react"
import Link from "next/link"
import { useEffect } from "react"
import type { CallbackStatus } from "@/lib/provider-auth"

const copy: Record<CallbackStatus, { title: string, body: string }> = {
  complete: { title: "Вход подтверждён", body: "Открываем ваше рабочее пространство…" },
  cancelled: { title: "Вход отменён", body: "Вы можете выбрать провайдера и попробовать снова." },
  denied: { title: "Доступ не предоставлен", body: "Провайдер не подтвердил вход. Проверьте выбранный аккаунт и повторите попытку." },
  provider_error: { title: "Не удалось завершить вход", body: "Провайдер недоступен или ещё не настроен для этого окружения." },
}

export function ProviderAuthCallback({ status }: { status: CallbackStatus }) {
  const message = copy[status]
  useEffect(() => {
    if (status !== "complete") return
    const timer = window.setTimeout(() => window.location.assign("/cabinet"), 250)
    return () => window.clearTimeout(timer)
  }, [status])
  const success = status === "complete"
  return <div className="space-y-4 text-center" aria-live="polite">
    <div className="flex justify-center">{success ? <CheckCircle2 className="size-9 text-emerald-600" /> : <AlertCircle className="size-9 text-destructive" />}</div>
    <div><h1 className="text-xl font-semibold">{message.title}</h1><p className="mt-2 text-sm text-muted-foreground">{message.body}</p></div>
    {success ? <div className="flex justify-center text-muted-foreground"><Loader2 className="size-5 animate-spin" /></div> : <Link className="inline-flex h-10 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground" href="/login">Вернуться к выбору провайдера</Link>}
  </div>
}
