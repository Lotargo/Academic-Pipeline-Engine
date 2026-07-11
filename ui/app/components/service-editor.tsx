"use client"

import Link from "next/link"
import { FormEvent, useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Ban, CheckCircle2, CircleAlert, FileClock, Loader2, Radio, Send, XCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Progress } from "@/components/ui/progress"
import { Textarea } from "@/components/ui/textarea"
import { startEditorRun } from "@/lib/editor-adapter"
import { jobRequest } from "@/lib/job-client"
import { activeJob, type EditorOptions, type Job, type JobEvent, type JobStatus } from "@/lib/job-contract"

const statuses: Record<JobStatus, { label: string; icon: typeof FileClock }> = {
  pending: { label: "Подготовка", icon: FileClock }, queued: { label: "В очереди", icon: FileClock }, running: { label: "Выполняется", icon: Radio }, succeeded: { label: "Готово", icon: CheckCircle2 }, failed: { label: "Ошибка", icon: XCircle }, cancelled: { label: "Отменено", icon: Ban },
}

export function ServiceEditor() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [topic, setTopic] = useState("")
  const [instructions, setInstructions] = useState("")
  const [academicMode, setAcademicMode] = useState(false)
  const [webSearch, setWebSearch] = useState(false)
  const [author, setAuthor] = useState("")
  const [artifact, setArtifact] = useState("")
  const [job, setJob] = useState<Job | null>(null)
  const [creating, setCreating] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const jobId = searchParams.get("job")

  useEffect(() => {
    if (!jobId) { setJob(null); return }
    let active = true
    void jobRequest<Job>(`/api/jobs/${encodeURIComponent(jobId)}`).then(next => { if (active) setJob(next) }).catch(cause => { if (active) setError(cause instanceof Error ? cause.message : "Задание недоступно.") })
    return () => { active = false }
  }, [jobId])

  useEffect(() => {
    if (!job || !activeJob(job)) return
    const stream = new EventSource(`/api/jobs/${encodeURIComponent(job.id)}/events`)
    stream.onmessage = event => { try { setJob((JSON.parse(event.data) as JobEvent).job) } catch { /* next event or refresh recovers the snapshot */ } }
    stream.onerror = () => stream.close()
    return () => stream.close()
  }, [job?.id, job?.status])

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!topic.trim()) return
    setCreating(true); setError(null)
    const editorOptions: EditorOptions = { academic_mode: academicMode, author: author.trim() || undefined, artifact_override: artifact || undefined, web_search_enabled: webSearch }
    try {
      const started = await startEditorRun({ topic, instructions, editorOptions })
      if (started.profile !== "service") throw new Error("Для service editor требуется service profile.")
      router.replace(`/?job=${encodeURIComponent(started.job.id)}`)
      setJob(started.job)
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Не удалось создать задание.") }
    finally { setCreating(false) }
  }

  async function cancel() {
    if (!job) return
    setCancelling(true); setError(null)
    try { setJob(await jobRequest<Job>(`/api/jobs/${encodeURIComponent(job.id)}/cancel`, { method: "POST" })) }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Не удалось запросить отмену.") }
    finally { setCancelling(false) }
  }

  return <main className="mx-auto min-h-svh max-w-6xl space-y-6 bg-muted/30 px-4 py-8 sm:px-6 lg:py-10">
    <div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-sm text-muted-foreground">Рабочее пространство</p><h1 className="mt-1 text-3xl font-bold tracking-tight">Редактор</h1><p className="mt-2 max-w-2xl text-sm text-muted-foreground">Создавайте задания в активном workspace. Статус, отмена и история используют тот же Job API, что и кабинет.</p></div><div className="flex gap-2"><Button asChild variant="outline"><Link href="/cabinet/jobs">Задания</Link></Button><Button asChild variant="outline"><Link href="/cabinet/history">История</Link></Button></div></div>
    {error && <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"><CircleAlert className="size-4" />{error}</div>}
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(19rem,.8fr)]"><Card><CardHeader><CardTitle>Новое задание</CardTitle><CardDescription>Расширенные параметры сохраняются вместе с job и доступны service worker без глобального состояния редактора.</CardDescription></CardHeader><CardContent><form className="space-y-5" onSubmit={create}><div className="space-y-2"><Label htmlFor="editor-topic">Тема</Label><Input id="editor-topic" value={topic} onChange={event => setTopic(event.target.value)} required disabled={creating} /></div><div className="space-y-2"><Label htmlFor="editor-instructions">Инструкции</Label><Textarea id="editor-instructions" value={instructions} onChange={event => setInstructions(event.target.value)} disabled={creating} placeholder="Цель, структура, стиль и ограничения" /></div><details className="rounded-lg border p-4"><summary className="cursor-pointer font-medium">Расширенные параметры</summary><div className="mt-4 grid gap-4 sm:grid-cols-2"><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={academicMode} onChange={event => setAcademicMode(event.target.checked)} />Академический режим</label><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={webSearch} onChange={event => setWebSearch(event.target.checked)} />Веб-поиск</label><div className="space-y-2"><Label htmlFor="editor-author">Автор</Label><Input id="editor-author" value={author} onChange={event => setAuthor(event.target.value)} maxLength={200} /></div><div className="space-y-2"><Label htmlFor="editor-artifact">Тип артефакта</Label><select id="editor-artifact" value={artifact} onChange={event => setArtifact(event.target.value)} className="h-9 w-full rounded-md border bg-background px-3 text-sm"><option value="">Автоопределение</option><option value="academic_paper">Статья</option><option value="technical_readme">README</option><option value="report">Отчёт</option><option value="plan_document">План</option><option value="unknown_freeform">Свободный формат</option></select></div></div></details><Button type="submit" disabled={creating}>{creating ? <Loader2 className="animate-spin" /> : <Send />}Создать задание</Button></form></CardContent></Card><JobSnapshot job={job} cancelling={cancelling} onCancel={cancel} /></div>
  </main>
}

function JobSnapshot({ job, cancelling, onCancel }: { job: Job | null; cancelling: boolean; onCancel: () => void }) {
  if (!job) return <Card className="h-fit"><CardContent className="py-12 text-center text-sm text-muted-foreground">После создания здесь появится живой статус задания.</CardContent></Card>
  const status = statuses[job.status]; const Icon = status.icon
  return <Card className="h-fit"><CardHeader><div className="flex items-start justify-between gap-3"><div><CardTitle className="break-words">{job.topic}</CardTitle><CardDescription className="mt-1 font-mono text-xs">{job.id}</CardDescription></div><span className="flex items-center gap-1.5 text-sm font-medium"><Icon className={`size-4 ${job.status === "running" ? "animate-spin text-ape-primary" : ""}`} />{status.label}</span></div></CardHeader><CardContent className="space-y-4"><div><div className="mb-2 flex justify-between text-sm"><span>{job.current_stage || "Ожидание worker"}</span><span className="font-mono">{job.progress}%</span></div><Progress value={job.progress} aria-label={`Прогресс: ${job.progress}%`} /></div><div className="flex flex-wrap gap-2"><Button asChild variant="outline" size="sm"><Link href={`/cabinet/jobs?job=${encodeURIComponent(job.id)}`}>Открыть в заданиях</Link></Button><Button asChild variant="outline" size="sm"><Link href="/cabinet/history">Открыть историю</Link></Button>{activeJob(job) && <Button variant="destructive" size="sm" onClick={onCancel} disabled={cancelling || Boolean(job.cancel_requested_at)}>{cancelling && <Loader2 className="animate-spin" />}{job.cancel_requested_at ? "Отмена запрошена" : "Запросить отмену"}</Button>}</div></CardContent></Card>
}
