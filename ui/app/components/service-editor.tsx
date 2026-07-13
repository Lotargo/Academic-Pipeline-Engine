"use client"

import Link from "next/link"
import { FormEvent, useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import {
  Ban,
  BookOpenText,
  CheckCircle2,
  CircleAlert,
  FileClock,
  FileText,
  GraduationCap,
  History,
  LibraryBig,
  Loader2,
  Radio,
  Send,
  Settings2,
  Sparkles,
  WandSparkles,
  XCircle,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Progress } from "@/components/ui/progress"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { startEditorRun } from "@/lib/editor-adapter"
import { jobRequest } from "@/lib/job-client"
import { activeJob, type EditorOptions, type Job, type JobEvent, type JobStatus } from "@/lib/job-contract"
import { parsePersonalSettings } from "@/lib/personal-settings"

const statuses: Record<JobStatus, { label: string; icon: typeof FileClock }> = {
  pending: { label: "Подготовка", icon: FileClock },
  queued: { label: "В очереди", icon: FileClock },
  running: { label: "Выполняется", icon: Radio },
  succeeded: { label: "Готово", icon: CheckCircle2 },
  failed: { label: "Ошибка", icon: XCircle },
  cancelled: { label: "Отменено", icon: Ban },
}

const artifactOptions = [
  { value: "auto", label: "Определить автоматически" },
  { value: "academic_paper", label: "Академическая статья" },
  { value: "report", label: "Отчёт" },
  { value: "technical_readme", label: "Технический README" },
  { value: "plan_document", label: "План документа" },
  { value: "unknown_freeform", label: "Свободный формат" },
]

const quickStarts = [
  { id: "academic_paper", label: "Научная статья", description: "Аргументированный академический текст", icon: GraduationCap, instructions: "Сформулируйте исследовательскую цель, методологию, структуру и требования к источникам." },
  { id: "report", label: "Отчёт", description: "Выводы, факты и рекомендации", icon: FileText, instructions: "Опишите контекст, ключевые данные, структуру отчёта и ожидаемые рекомендации." },
  { id: "technical_readme", label: "README", description: "Документация для проекта", icon: LibraryBig, instructions: "Укажите аудиторию, установку, примеры использования и ограничения проекта." },
]

type JobsResponse = { jobs: Job[] }

export function ServiceEditor() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [topic, setTopic] = useState("")
  const [instructions, setInstructions] = useState("")
  const [academicMode, setAcademicMode] = useState(false)
  const [webSearch, setWebSearch] = useState(false)
  const [author, setAuthor] = useState("")
  const [artifact, setArtifact] = useState("auto")
  const [job, setJob] = useState<Job | null>(null)
  const [recentJobs, setRecentJobs] = useState<Job[]>([])
  const [creating, setCreating] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const jobId = searchParams.get("job")

  useEffect(() => {
    let active = true
    void Promise.all([
      fetch("/api/settings/me", { cache: "no-store" }).then(response => response.ok ? response.json() : null),
      jobRequest<JobsResponse>("/api/jobs").catch(() => ({ jobs: [] })),
    ]).then(([settings, jobs]) => {
      if (!active) return
      const parsed = parsePersonalSettings(settings)
      if (parsed) {
        const defaults = parsed.editor_defaults
        setAcademicMode(Boolean(defaults.academic_mode))
        setWebSearch(Boolean(defaults.web_search_enabled))
        setAuthor(current => current || defaults.author || "")
        setArtifact(current => current === "auto" ? defaults.artifact_override || "auto" : current)
      }
      setRecentJobs(jobs.jobs.slice(0, 4))
    })
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (!jobId) { setJob(null); return }
    let active = true
    void jobRequest<Job>(`/api/jobs/${encodeURIComponent(jobId)}`)
      .then(next => { if (active) setJob(next) })
      .catch(cause => { if (active) setError(cause instanceof Error ? cause.message : "Задание недоступно.") })
    return () => { active = false }
  }, [jobId])

  useEffect(() => {
    if (!job || !activeJob(job)) return
    const stream = new EventSource(`/api/jobs/${encodeURIComponent(job.id)}/events`)
    stream.onmessage = event => {
      try { setJob((JSON.parse(event.data) as JobEvent).job) } catch { /* a later event or refresh recovers the snapshot */ }
    }
    stream.onerror = () => stream.close()
    return () => stream.close()
  }, [job?.id, job?.status])

  function applyQuickStart(id: string, defaultInstructions: string) {
    setArtifact(id)
    setInstructions(current => current.trim() ? current : defaultInstructions)
  }

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!topic.trim()) return
    setCreating(true)
    setError(null)
    const editorOptions: EditorOptions = {
      academic_mode: academicMode,
      author: author.trim() || undefined,
      artifact_override: artifact === "auto" ? undefined : artifact,
      web_search_enabled: webSearch,
    }
    try {
      const started = await startEditorRun({ topic, instructions, editorOptions })
      if (started.profile !== "service") throw new Error("Для service editor требуется service profile.")
      router.replace(`/?job=${encodeURIComponent(started.job.id)}`)
      setJob(started.job)
      setRecentJobs(current => [started.job, ...current.filter(item => item.id !== started.job.id)].slice(0, 4))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Не удалось создать задание.")
    } finally {
      setCreating(false)
    }
  }

  async function cancel() {
    if (!job) return
    setCancelling(true)
    setError(null)
    try {
      setJob(await jobRequest<Job>(`/api/jobs/${encodeURIComponent(job.id)}/cancel`, { method: "POST" }))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Не удалось запросить отмену.")
    } finally {
      setCancelling(false)
    }
  }

  return <main className="mx-auto min-h-svh max-w-[96rem] space-y-6 bg-muted/30 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
    <header className="flex flex-wrap items-start justify-between gap-4 rounded-xl border bg-card px-5 py-5 shadow-sm">
      <div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground"><Sparkles className="size-4 text-ape-primary" />Рабочее пространство</div>
        <h1 className="mt-1 text-3xl font-bold tracking-tight">Новый документ</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">Соберите краткое задание, выберите формат и запустите pipeline. Все параметры сохраняются только в этой job и остаются внутри вашего workspace.</p>
      </div>
      <div className="flex flex-wrap gap-2"><Button asChild variant="outline"><Link href="/cabinet/jobs">Задания</Link></Button><Button asChild variant="outline"><Link href="/cabinet/history">История</Link></Button><Button asChild variant="outline"><Link href="/cabinet/settings"><Settings2 />Настройки</Link></Button></div>
    </header>

    {error && <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"><CircleAlert className="size-4" />{error}</div>}

    <div className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(21rem,.72fr)]">
      <Card>
        <CardHeader className="border-b pb-5"><CardTitle className="flex items-center gap-2"><WandSparkles className="size-5 text-ape-primary" />Соберите задание</CardTitle><CardDescription>Начните с подходящего формата или опишите документ в свободной форме. Расширенные настройки не являются глобальными.</CardDescription></CardHeader>
        <CardContent className="pt-6">
          <div className="grid gap-3 sm:grid-cols-3">
            {quickStarts.map(({ id, label, description, icon: Icon, instructions: quickInstructions }) => <button key={id} type="button" onClick={() => applyQuickStart(id, quickInstructions)} aria-pressed={artifact === id} className={`rounded-lg border p-4 text-left transition-colors hover:border-ape-primary hover:bg-ape-primary-soft/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${artifact === id ? "border-ape-primary bg-ape-primary-soft/40" : "bg-background"}`}><Icon className="size-5 text-ape-primary" /><p className="mt-3 text-sm font-semibold">{label}</p><p className="mt-1 text-xs text-muted-foreground">{description}</p></button>)}
          </div>
          <form className="mt-6 space-y-5" onSubmit={create}>
            <div className="grid gap-5 md:grid-cols-[minmax(0,1fr)_15rem]">
              <div className="space-y-2"><Label htmlFor="editor-topic">Тема или рабочее название</Label><Input id="editor-topic" value={topic} onChange={event => setTopic(event.target.value)} required disabled={creating} placeholder="Например, влияние ... на ..." className="h-11" /></div>
              <div className="space-y-2"><Label htmlFor="editor-artifact">Формат</Label><Select value={artifact} onValueChange={setArtifact} disabled={creating}><SelectTrigger id="editor-artifact" className="h-11"><SelectValue /></SelectTrigger><SelectContent>{artifactOptions.map(option => <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>)}</SelectContent></Select></div>
            </div>
            <div className="space-y-2"><div className="flex items-center justify-between gap-3"><Label htmlFor="editor-instructions">Задача для документа</Label><span className="text-xs text-muted-foreground">Цель, структура, стиль, факты и ограничения</span></div><Textarea id="editor-instructions" value={instructions} onChange={event => setInstructions(event.target.value)} disabled={creating} placeholder="Опишите, для кого предназначен текст, какие вопросы нужно раскрыть и какой результат ожидается." className="min-h-40 resize-y" /></div>
            <details className="rounded-lg border bg-muted/20 p-4"><summary className="cursor-pointer list-none font-medium marker:hidden"><span className="flex items-center gap-2"><BookOpenText className="size-4 text-ape-primary" />Параметры запуска</span></summary><div className="mt-5 grid gap-5 md:grid-cols-2"><div className="space-y-2"><Label htmlFor="editor-author">Автор</Label><Input id="editor-author" value={author} onChange={event => setAuthor(event.target.value)} disabled={creating} maxLength={200} placeholder="Необязательно" /></div><div className="rounded-lg border bg-background p-4"><div className="flex items-start justify-between gap-4"><div><Label htmlFor="editor-academic">Академический режим</Label><p className="mt-1 text-xs text-muted-foreground">Строже оформляет структуру и требования к изложению.</p></div><Switch id="editor-academic" checked={academicMode} onCheckedChange={setAcademicMode} disabled={creating} /></div></div><div className="rounded-lg border bg-background p-4 md:col-span-2"><div className="flex items-start justify-between gap-4"><div><Label htmlFor="editor-web-search">Веб-поиск</Label><p className="mt-1 text-xs text-muted-foreground">Разрешить pipeline подобрать внешние источники, если выбранный provider и worker это поддерживают.</p></div><Switch id="editor-web-search" checked={webSearch} onCheckedChange={setWebSearch} disabled={creating} /></div></div></div></details>
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-muted/40 p-4"><p className="text-xs text-muted-foreground">После запуска текст задания и параметры станут частью snapshot job. Их можно открыть из «Заданий» и «Истории».</p><Button type="submit" size="lg" disabled={creating}>{creating ? <Loader2 className="animate-spin" /> : <Send />}Создать задание</Button></div>
          </form>
        </CardContent>
      </Card>
      <aside className="space-y-6"><JobSnapshot job={job} cancelling={cancelling} onCancel={cancel} /><RecentJobs jobs={recentJobs} /></aside>
    </div>
  </main>
}

function RecentJobs({ jobs }: { jobs: Job[] }) {
  return <Card><CardHeader><CardTitle className="flex items-center gap-2 text-lg"><History className="size-5 text-ape-primary" />Недавние задания</CardTitle><CardDescription>Только из текущего workspace.</CardDescription></CardHeader><CardContent>{jobs.length === 0 ? <p className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">Заданий пока нет. Первый запуск появится здесь и в истории.</p> : <div className="space-y-3">{jobs.map(item => { const status = statuses[item.status]; return <Link key={item.id} href={`/?job=${encodeURIComponent(item.id)}`} className="block rounded-lg border p-3 transition-colors hover:bg-accent"><div className="flex items-start justify-between gap-3"><p className="line-clamp-2 text-sm font-medium">{item.topic}</p><Badge variant="secondary" className="shrink-0">{status.label}</Badge></div><p className="mt-2 text-xs text-muted-foreground">{item.current_stage || "Ожидает запуска"} · {item.progress}%</p></Link> })}</div>}</CardContent></Card>
}

function JobSnapshot({ job, cancelling, onCancel }: { job: Job | null; cancelling: boolean; onCancel: () => void }) {
  if (!job) return <Card className="overflow-hidden"><CardHeader className="bg-gradient-to-br from-ape-primary-soft/60 to-transparent"><CardTitle className="text-lg">Статус выполнения</CardTitle><CardDescription>После запуска здесь появится живая стадия, прогресс и быстрые действия.</CardDescription></CardHeader><CardContent className="space-y-4 py-6"><div className="grid grid-cols-3 gap-2 text-center text-xs text-muted-foreground"><div className="rounded-md border bg-background p-3">1<br /><span className="font-medium text-foreground">Задание</span></div><div className="rounded-md border bg-background p-3">2<br /><span className="font-medium text-foreground">Pipeline</span></div><div className="rounded-md border bg-background p-3">3<br /><span className="font-medium text-foreground">История</span></div></div><p className="text-sm text-muted-foreground">Редактор не читает глобальный статус: он показывает только выбранную job из вашего workspace.</p></CardContent></Card>
  const status = statuses[job.status]
  const Icon = status.icon
  return <Card className="overflow-hidden"><CardHeader className="border-b"><div className="flex items-start justify-between gap-3"><div><CardTitle className="break-words text-lg">{job.topic}</CardTitle><CardDescription className="mt-1 font-mono text-xs">{job.id}</CardDescription></div><span className="flex items-center gap-1.5 text-sm font-medium"><Icon className={`size-4 ${job.status === "running" ? "animate-spin text-ape-primary" : ""}`} />{status.label}</span></div></CardHeader><CardContent className="space-y-4 pt-5"><div><div className="mb-2 flex justify-between text-sm"><span>{job.current_stage || "Ожидание worker"}</span><span className="font-mono">{job.progress}%</span></div><Progress value={job.progress} aria-label={`Прогресс: ${job.progress}%`} /></div><div className="flex flex-wrap gap-2"><Button asChild variant="outline" size="sm"><Link href={`/cabinet/jobs?job=${encodeURIComponent(job.id)}`}>Открыть задание</Link></Button><Button asChild variant="outline" size="sm"><Link href="/cabinet/history">История</Link></Button>{activeJob(job) && <Button variant="destructive" size="sm" onClick={onCancel} disabled={cancelling || Boolean(job.cancel_requested_at)}>{cancelling && <Loader2 className="animate-spin" />}{job.cancel_requested_at ? "Отмена запрошена" : "Запросить отмену"}</Button>}</div></CardContent></Card>
}
