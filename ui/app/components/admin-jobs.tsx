"use client"

import { useCallback, useEffect, useState } from "react"
import { CircleAlert, ClipboardList, Loader2, RefreshCw, RotateCcw } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { adminJobsSnapshot, type AdminJobsSnapshot } from "@/lib/admin-jobs-contract"

const statusLabel = { pending: "Ожидает", queued: "В очереди", running: "Выполняется", succeeded: "Завершено", failed: "Ошибка", cancelled: "Отменено" }

export function AdminJobs() {
  const [snapshot, setSnapshot] = useState<AdminJobsSnapshot | null>(null)
  const [error, setError] = useState<string | null>(null)
  const load = useCallback(async () => {
    setError(null)
    try {
      const response = await fetch("/api/admin/jobs", { cache: "no-store" })
      if (!response.ok) throw new Error(response.status === 403 ? "Недостаточно прав для просмотра очередей." : "Не удалось загрузить состояние заданий.")
      setSnapshot(adminJobsSnapshot.parse(await response.json()))
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Не удалось загрузить состояние заданий.") }
  }, [])
  useEffect(() => {
    const requestId = window.setTimeout(() => { void load() }, 0)
    return () => window.clearTimeout(requestId)
  }, [load])
  const total = snapshot?.jobs.reduce((sum, item) => sum + item.count, 0) ?? 0

  return <section className="space-y-6"><div><p className="text-sm text-muted-foreground">Администрирование</p><h1 className="mt-1 text-3xl font-bold tracking-tight">Очереди и задания</h1><p className="mt-2 text-muted-foreground">Агрегированное состояние lifecycle и transactional outbox. Содержимое заданий не отображается.</p></div>{error && <Alert variant="destructive"><CircleAlert /><AlertTitle>Данные недоступны</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}<div className="grid gap-4 sm:grid-cols-2"><Card><CardHeader><CardTitle className="flex items-center gap-2 text-base"><ClipboardList className="size-5 text-ape-primary" />Всего заданий</CardTitle><CardDescription>Все workspace и terminal states.</CardDescription></CardHeader><CardContent>{snapshot ? <p className="text-3xl font-semibold">{total}</p> : <Loading />}</CardContent></Card><Card><CardHeader><CardTitle className="flex items-center gap-2 text-base"><RotateCcw className="size-5 text-ape-primary" />Непубликованные события</CardTitle><CardDescription>Outbox — источник публикации, не broker.</CardDescription></CardHeader><CardContent>{snapshot ? <p className="text-3xl font-semibold">{snapshot.queues.reduce((sum, queue) => sum + queue.pending, 0)}</p> : <Loading />}</CardContent></Card></div><Card><CardHeader className="flex-row items-start justify-between gap-4"><div><CardTitle>Lifecycle заданий</CardTitle><CardDescription>Только счётчики: без topic, instructions, ошибок и иных данных workspace.</CardDescription></div><Button variant="outline" size="sm" onClick={() => void load()}><RefreshCw />Обновить</Button></CardHeader><CardContent>{snapshot === null && !error ? <Loading /> : <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{snapshot?.jobs.map(item => <div key={item.status} className="rounded-lg border p-4"><p className="text-sm text-muted-foreground">{statusLabel[item.status]}</p><p className="mt-1 text-2xl font-semibold">{item.count}</p></div>)}</div>}</CardContent></Card><Card><CardHeader><CardTitle>Очереди outbox</CardTitle><CardDescription>Повторные публикации учитываются отдельно.</CardDescription></CardHeader><CardContent>{snapshot === null && !error ? <Loading /> : snapshot?.queues.length === 0 ? <p className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">Непубликованных событий нет.</p> : <div className="space-y-3">{snapshot?.queues.map(queue => <article key={queue.workload} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-4"><div><h2 className="font-mono text-sm font-semibold">{queue.workload}</h2><p className="mt-1 text-sm text-muted-foreground">Ожидают публикации: {queue.pending}</p></div><Badge variant={queue.retrying ? "outline" : "secondary"}>Повторов: {queue.retrying}</Badge></article>)}</div>}</CardContent></Card></section>
}

function Loading() { return <div className="flex items-center justify-center gap-2 py-6 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" />Загружаем данные…</div> }
