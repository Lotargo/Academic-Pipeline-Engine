"use client"

import { useCallback, useEffect, useState } from "react"
import { Bot, CircleAlert, Gauge, Loader2, RefreshCw, ShieldCheck } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { adminResourceSnapshot, type AdminResourceSnapshot } from "@/lib/admin-resource-contract"

const availabilityLabel = { available: "Доступен", degraded: "Ограничен", exhausted: "Исчерпан", unavailable: "Недоступен" }
const healthLabel = { healthy: "Исправен", degraded: "Деградация", open: "Отключён circuit breaker", unknown: "Неизвестно" }

export function AdminResources() {
  const [snapshot, setSnapshot] = useState<AdminResourceSnapshot | null>(null)
  const [error, setError] = useState<string | null>(null)
  const load = useCallback(async () => {
    setError(null)
    try {
      const response = await fetch("/api/admin/resources", { cache: "no-store" })
      if (!response.ok) throw new Error(response.status === 403 ? "Недостаточно прав для просмотра ресурсов." : "Не удалось загрузить ресурсы платформы.")
      setSnapshot(adminResourceSnapshot.parse(await response.json()))
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Не удалось загрузить ресурсы платформы.") }
  }, [])
  useEffect(() => {
    const requestId = window.setTimeout(() => { void load() }, 0)
    return () => window.clearTimeout(requestId)
  }, [load])

  return <section className="space-y-6"><div><p className="text-sm text-muted-foreground">Администрирование</p><h1 className="mt-1 text-3xl font-bold tracking-tight">Провайдеры и ресурсы</h1><p className="mt-2 text-muted-foreground">Состояние моделей, доступности и fair-use политики. Секреты и пользовательские ключи не отображаются.</p></div>{error && <Alert variant="destructive"><CircleAlert /><AlertTitle>Данные недоступны</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}<div className="grid gap-4 sm:grid-cols-2"><Card><CardHeader><CardTitle className="flex items-center gap-2 text-base"><Gauge className="size-5 text-ape-primary" />Fair-use</CardTitle><CardDescription>Общие ограничения для одного пользователя.</CardDescription></CardHeader><CardContent>{snapshot ? <dl className="grid grid-cols-2 gap-4 text-sm"><div><dt className="text-muted-foreground">Активных заданий</dt><dd className="mt-1 text-2xl font-semibold">{snapshot.fair_use.max_active_per_user}</dd></div><div><dt className="text-muted-foreground">В очереди</dt><dd className="mt-1 text-2xl font-semibold">{snapshot.fair_use.max_queued_per_user}</dd></div></dl> : <Loading />}</CardContent></Card><Card><CardHeader><CardTitle className="flex items-center gap-2 text-base"><ShieldCheck className="size-5 text-ape-primary" />Безопасность</CardTitle><CardDescription>Snapshot доступен только admin JWT.</CardDescription></CardHeader><CardContent className="text-sm text-muted-foreground">Изменение лимитов и platform credentials пока не предусмотрено API и требует отдельного аудируемого контракта.</CardContent></Card></div><Card><CardHeader className="flex-row items-start justify-between gap-4"><div><CardTitle className="flex items-center gap-2"><Bot className="size-5 text-ape-primary" />Ресурсы провайдеров</CardTitle><CardDescription>Unknown quota не интерпретируется как точный баланс.</CardDescription></div><Button variant="outline" size="sm" onClick={() => void load()}><RefreshCw />Обновить</Button></CardHeader><CardContent>{snapshot === null && !error ? <Loading /> : snapshot?.providers.length === 0 ? <p className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">Провайдеры ещё не зарегистрированы в service profile.</p> : <div className="space-y-3">{snapshot?.providers.map(provider => <article key={provider.id} className="rounded-lg border p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="font-semibold">{provider.display_name}</h2><p className="mt-1 font-mono text-xs text-muted-foreground">{provider.id}</p></div><div className="flex flex-wrap gap-2"><Badge variant={provider.availability === "available" ? "secondary" : "outline"}>{availabilityLabel[provider.availability]}</Badge><Badge variant="outline">{healthLabel[provider.health]}</Badge></div></div><div className="mt-4 grid gap-4 text-sm md:grid-cols-3"><div><p className="text-muted-foreground">Модели</p><p className="mt-1">{provider.models.length ? provider.models.map(model => model.id).join(", ") : "Нет моделей"}</p></div><div><p className="text-muted-foreground">Бюджет</p><p className="mt-1">{provider.budget.kind === "known" ? `${provider.budget.used} из ${provider.budget.limit}` : "Неизвестная квота"}</p></div><div><p className="text-muted-foreground">Platform credential</p><p className="mt-1">{provider.platform_credential ? "Настроен" : "Не настроен"}</p></div></div></article>)}</div>}</CardContent></Card></section>
}

function Loading() { return <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" />Загружаем данные…</div> }
