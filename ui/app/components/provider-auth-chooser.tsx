"use client"

import { FileCheck2, Loader2, Mail } from "lucide-react"
import { type FormEvent, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type { ProviderAuthMode, ProviderId } from "@/lib/provider-auth"

const labels: Record<ProviderId, string> = { google: "Продолжить с Google", yandex: "Продолжить с Яндексом" }

function GoogleIcon() {
  return <svg aria-hidden="true" className="size-5" viewBox="0 0 24 24"><path fill="#4285f4" d="M21.6 12.23c0-.71-.06-1.23-.2-1.77H12v3.34h5.52c-.11.83-.72 2.08-2.08 2.92l-.02.11 3.02 2.35.21.02c1.93-1.78 2.95-4.4 2.95-7.97Z"/><path fill="#34a853" d="M12 22c2.7 0 4.97-.89 6.63-2.4l-3.21-2.49c-.86.6-2.01 1.02-3.42 1.02a6 6 0 0 1-5.68-4.15l-.1.01-3.14 2.44-.03.1A10 10 0 0 0 12 22Z"/><path fill="#fbbc05" d="M6.32 14a6.06 6.06 0 0 1 0-3.98v-.12L3.15 7.43l-.1.05A10 10 0 0 0 3 12c0 1.61.39 3.14 1.05 4.52L6.32 14Z"/><path fill="#ea4335" d="M12 5.88c1.78 0 2.98.77 3.67 1.42l2.68-2.61C16.96 3.39 14.7 2.6 12 2.6a10 10 0 0 0-8.95 5.53l3.27 2.53A6 6 0 0 1 12 5.88Z"/></svg>
}

function YandexIcon() {
  return <span aria-hidden="true" className="grid size-5 place-items-center rounded-full bg-[#fc3f1d] font-serif text-sm font-bold leading-none text-white">Я</span>
}

export function ProviderAuthChooser({ mode }: { mode: ProviderAuthMode }) {
  const [providerPending, setProviderPending] = useState<ProviderId | null>(null)
  const [emailPending, setEmailPending] = useState(false)
  const [email, setEmail] = useState("")
  const [emailError, setEmailError] = useState<string | null>(null)

  const start = (provider: ProviderId) => {
    setProviderPending(provider)
    window.location.assign(`/api/auth/providers/${provider}/start`)
  }

  const submitEmail = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setEmailError(null)
    setEmailPending(true)
    try {
      const response = await fetch("/api/auth/email/start", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email }),
      })
      const payload = await response.json().catch(() => null) as { detail?: unknown } | null
      if (!response.ok) {
        setEmailError(typeof payload?.detail === "string" ? payload.detail : "Не удалось продолжить с этим email")
        return
      }
      window.location.assign("/cabinet")
    } catch {
      setEmailError("Сервис входа временно недоступен")
    } finally {
      setEmailPending(false)
    }
  }

  const pending = providerPending !== null || emailPending
  return <div className="space-y-5">
    <div className="rounded-lg border bg-muted/35 p-4">
      <div className="mb-2 flex items-center gap-2 text-sm font-medium"><FileCheck2 className="size-4 text-primary"/>Рабочее пространство для академических материалов</div>
      <p className="text-sm leading-6 text-muted-foreground">Собирайте документы, запускайте проверки, отслеживайте версии и готовьте экспорт в одном personal workspace.</p>
    </div>
    {mode === "mock" && <p className="rounded-md border border-amber-400/40 bg-amber-50 px-3 py-2 text-sm text-amber-950 dark:bg-amber-950/30 dark:text-amber-100">Режим service-dev: Google, Яндекс и email эмулируются локально. Письма, коды и данные OAuth не отправляются.</p>}
    <div className="space-y-3">
      {(["google", "yandex"] as const).map(provider => <Button key={provider} type="button" variant="outline" className="h-12 w-full justify-start px-4 font-medium" disabled={pending} onClick={() => start(provider)}>
        {providerPending === provider ? <Loader2 className="size-5 animate-spin"/> : provider === "google" ? <GoogleIcon/> : <YandexIcon/>}
        <span className="flex-1 text-center">{labels[provider]}</span><span className="size-5" aria-hidden="true"/>
      </Button>)}
    </div>
    {mode === "mock" && <>
      <div className="flex items-center gap-3 text-xs text-muted-foreground before:h-px before:flex-1 before:bg-border after:h-px after:flex-1 after:bg-border">или</div>
      <form className="space-y-3" onSubmit={submitEmail}>
        <label className="sr-only" htmlFor="email">Email</label>
        <div className="relative"><Mail aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"/><Input id="email" name="email" type="email" autoComplete="email" placeholder="you@example.com" className="h-12 pl-10" value={email} maxLength={320} required disabled={pending} onChange={event => setEmail(event.target.value)}/></div>
        <Button type="submit" className="h-12 w-full" disabled={pending}>{emailPending ? <Loader2 className="animate-spin"/> : <Mail/>}Продолжить с email</Button>
        {emailError && <p role="alert" className="text-sm text-destructive">{emailError}</p>}
        <p className="text-center text-xs leading-5 text-muted-foreground">Новый адрес создаст personal workspace, существующий — откроет его. Подтверждение email появится после настройки почтового сервиса.</p>
      </form>
    </>}
    <p className="text-center text-xs leading-5 text-muted-foreground">Продолжая, вы соглашаетесь с правилами использования Academic PE. Пароли не собираются и не хранятся в этом профиле.</p>
  </div>
}
