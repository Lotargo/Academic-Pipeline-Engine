"use client"

import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { FormEvent, useCallback, useEffect, useRef, useState } from "react"
import { Ban, CheckCircle2, CircleAlert, Clock3, Loader2, Radio, RefreshCw, Send, XCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Progress } from "@/components/ui/progress"
import { Textarea } from "@/components/ui/textarea"
import { createEditorJob, jobRequest } from "@/lib/job-client"
import { activeJob, type Job, type JobEvent, type JobStatus } from "@/lib/job-contract"

const rememberedJob = "ape.active-job"
const terminal = new Set<JobStatus>(["succeeded", "failed", "cancelled"])
const statusLabel: Record<JobStatus, string> = { pending: "Подготовка", queued: "В очереди", running: "Выполняется", succeeded: "Готово", failed: "Ошибка", cancelled: "Отменено" }
const statusIcon: Record<JobStatus, typeof Clock3> = { pending: Clock3, queued: Clock3, running: Loader2, succeeded: CheckCircle2, failed: XCircle, cancelled: Ban }

function message(error: unknown) { return error instanceof Error ? error.message : "Не удалось выполнить запрос." }

export function JobsWorkspace() {
  const searchParams = useSearchParams()
  const [jobs, setJobs] = useState<Job[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [topic, setTopic] = useState("")
  const [instructions, setInstructions] = useState("")
  const [creating, setCreating] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [transport, setTransport] = useState<"loading" | "live" | "polling">("loading")
  const lastEvent = useRef<string | null>(null)
  const requestedJobId = searchParams.get("job")
  const selected = jobs.find(job => job.id === selectedId) ?? null

  const upsert = useCallback((job: Job) => setJobs(previous => [job, ...previous.filter(item => item.id !== job.id)]), [])
  const load = useCallback(async (id?: string | null) => {
    try {
      if (id) { const job = await jobRequest<Job>(`/api/jobs/${id}`); upsert(job); setSelectedId(job.id); return job }
      const data = await jobRequest<{ jobs: Job[] }>("/api/jobs")
      setJobs(data.jobs); const saved = sessionStorage.getItem(rememberedJob); const initial = data.jobs.find(job => job.id === saved) ?? data.jobs.find(activeJob) ?? data.jobs[0]
      setSelectedId(initial?.id ?? null); return initial
    } catch (cause) { setError(message(cause)); return undefined }
  }, [upsert])

  useEffect(() => { void load(requestedJobId) }, [load, requestedJobId])
  useEffect(() => { if (selected && activeJob(selected)) sessionStorage.setItem(rememberedJob, selected.id); else if (selected) sessionStorage.removeItem(rememberedJob) }, [selected])

  useEffect(() => {
    if (!selected || terminal.has(selected.status)) { setTransport("loading"); return }
    let closed = false; let retry = 1000; let source: EventSource | null = null; let poll: ReturnType<typeof setInterval> | null = null; let retryTimer: ReturnType<typeof setTimeout> | null = null
    const snapshot = () => void load(selected.id)
    const polling = () => { if (closed) return; setTransport("polling"); snapshot(); poll ??= setInterval(snapshot, 5000) }
    const connect = () => {
      if (closed || !("EventSource" in window)) return polling()
      const resume = lastEvent.current ? `?last_event_id=${encodeURIComponent(lastEvent.current)}` : ""
      source = new EventSource(`/api/jobs/${selected.id}/events${resume}`)
      source.onopen = () => { retry = 1000; setTransport("live"); if (poll) { clearInterval(poll); poll = null } }
      source.onmessage = event => {
        if (event.lastEventId && event.lastEventId === lastEvent.current) return
        try { const update = JSON.parse(event.data) as JobEvent; lastEvent.current = event.lastEventId || update.id; upsert(update.job) } catch { snapshot() }
      }
      source.onerror = () => { source?.close(); polling(); retryTimer = setTimeout(connect, retry); retry = Math.min(retry * 2, 30000) }
    }
    connect()
    return () => { closed = true; source?.close(); if (poll) clearInterval(poll); if (retryTimer) clearTimeout(retryTimer) }
  }, [selected?.id, selected?.status, load, upsert])

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!topic.trim()) return; setCreating(true); setError(null)
    try { const job = await createEditorJob(topic, instructions); upsert(job); setSelectedId(job.id); setTopic(""); setInstructions("") } catch (cause) { setError(message(cause)) } finally { setCreating(false) }
  }
  async function cancel() {
    if (!selected) return; setCancelling(true); setError(null)
    try { upsert(await jobRequest<Job>(`/api/jobs/${selected.id}/cancel`, { method: "POST" })) } catch (cause) { setError(message(cause)) } finally { setCancelling(false) }
  }

  return <section className="mx-auto max-w-6xl space-y-6">
    <div><p className="text-sm text-muted-foreground">Pipeline</p><h1 className="text-3xl font-bold tracking-tight">Задания и живой статус</h1><p className="mt-2 text-sm text-muted-foreground">Создайте задачу, следите за этапами и безопасно запросите отмену.</p></div>
    {error && <div className="flex items-center gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"><CircleAlert className="size-4 shrink-0" />{error}<Button className="ml-auto" size="sm" variant="outline" onClick={() => { setError(null); void load(selectedId) }}><RefreshCw />Повторить</Button></div>}
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(20rem,0.85fr)]">
      <Card><CardHeader><CardTitle>Новое задание</CardTitle><CardDescription>Сервер подтвердит создание и вернёт ID задания. Прогресс обновляет только worker.</CardDescription></CardHeader><CardContent><form className="space-y-4" onSubmit={create}><div className="space-y-2"><Label htmlFor="job-topic">Тема</Label><Input id="job-topic" value={topic} onChange={event => setTopic(event.target.value)} placeholder="Например, сравнительный обзор методов" required disabled={creating} /></div><div className="space-y-2"><Label htmlFor="job-instructions">Дополнительные инструкции <span className="text-muted-foreground">(необязательно)</span></Label><Textarea id="job-instructions" value={instructions} onChange={event => setInstructions(event.target.value)} placeholder="Требования к структуре, языку или источникам" disabled={creating} /></div><Button disabled={creating}>{creating ? <Loader2 className="animate-spin" /> : <Send />}Создать задание</Button></form></CardContent></Card>
      <Card><CardHeader><CardTitle className="flex items-center gap-2"><Radio className={transport === "live" ? "size-4 text-ape-primary" : "size-4 text-muted-foreground"} />{transport === "live" ? "Подключено к live events" : transport === "polling" ? "Обновление каждые 5 секунд" : "Ожидание статуса"}</CardTitle><CardDescription>При разрыве потока автоматически включается polling и попытка переподключения.</CardDescription></CardHeader><CardContent>{jobs.length ? <div className="space-y-2">{jobs.map(job => <button key={job.id} onClick={() => setSelectedId(job.id)} className={`w-full rounded-lg border p-3 text-left transition-colors ${selectedId === job.id ? "border-ape-primary bg-ape-primary-soft" : "hover:bg-muted"}`}><div className="flex items-center justify-between gap-3"><span className="truncate font-medium">{job.topic}</span><JobStatusBadge status={job.status} /></div><p className="mt-1 font-mono text-xs text-muted-foreground">{job.id}</p></button>)}</div> : <p className="text-sm text-muted-foreground">Активных заданий пока нет.</p>}</CardContent></Card>
    </div>
    <JobDetails job={selected} cancelling={cancelling} onCancel={cancel} />
  </section>
}

function JobStatusBadge({ status }: { status: JobStatus }) { const Icon = statusIcon[status]; return <span className="flex shrink-0 items-center gap-1.5 text-xs font-semibold"><Icon className={`size-3.5 ${status === "running" ? "animate-spin text-ape-primary" : ""}`} />{statusLabel[status]}</span> }
function JobDetails({ job, cancelling, onCancel }: { job: Job | null; cancelling: boolean; onCancel: () => void }) {
  if (!job) return <Card><CardContent className="py-10 text-center text-sm text-muted-foreground">Выберите задание, чтобы открыть его статус.</CardContent></Card>
  const cancellationRequested = Boolean(job.cancel_requested_at)
  return <Card><CardHeader><div className="flex flex-wrap items-start justify-between gap-3"><div><CardTitle>{job.topic}</CardTitle><CardDescription className="mt-1 font-mono">{job.id}</CardDescription></div><JobStatusBadge status={job.status} /></div></CardHeader><CardContent className="space-y-5"><div><div className="mb-2 flex justify-between text-sm"><span>{job.current_stage ? `Этап: ${job.current_stage}` : "Этап ещё не начат"}</span><span className="font-mono">{job.progress}%</span></div><Progress value={job.progress} aria-label={`Прогресс: ${job.progress}%`} /></div>{job.stages.length > 0 && <ol className="space-y-2">{job.stages.map(stage => <li key={stage.name} className="flex items-center justify-between rounded-md bg-muted/50 px-3 py-2 text-sm"><span>{stage.name}</span><span className="font-mono text-muted-foreground">{stage.progress}% · {stage.status}</span></li>)}</ol>}{job.error_message && <p className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">{job.error_message}</p>}<div className="flex flex-wrap gap-2 border-t pt-4"><Button asChild variant="outline" size="sm"><Link href={`/?job=${encodeURIComponent(job.id)}`}>Открыть в редакторе</Link></Button>{activeJob(job) && (cancellationRequested ? <p className="self-center text-sm text-muted-foreground">Отмена запрошена. Worker завершит текущую безопасную операцию и подтвердит статус.</p> : <Button variant="destructive" onClick={onCancel} disabled={cancelling}>{cancelling && <Loader2 className="animate-spin" />}Запросить отмену</Button>)}</div></CardContent></Card>
}
