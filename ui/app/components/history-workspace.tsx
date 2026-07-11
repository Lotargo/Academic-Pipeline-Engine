"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { Archive, CircleAlert, Download, FileText, Loader2, RefreshCw, Trash2 } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog"
import type { Artifact, HistoryItem, HistoryPage } from "@/lib/history-contract"

async function api<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, headers: { "content-type": "application/json", ...init?.headers }, cache: "no-store" })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    const error = new Error(body.detail || "Не удалось выполнить запрос.")
    ;(error as Error & { status?: number }).status = response.status
    throw error
  }
  return response.status === 204 ? undefined as T : response.json() as Promise<T>
}

const statusLabels: Record<string, string> = { succeeded: "Готово", failed: "Ошибка", cancelled: "Отменено" }
const formatDate = (value: string) => new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value))
const formatSize = (size: number | null) => size == null ? "Размер неизвестен" : new Intl.NumberFormat("ru-RU", { style: "unit", unit: "megabyte", maximumFractionDigits: 1 }).format(size / 1024 / 1024)

function legacyArtifact(id: string, name: unknown, kind: string, size: unknown, runId: unknown): Artifact | null {
  if (typeof name !== "string" || !name) return null
  return {
    id: `legacy:${id}:${name}`,
    name,
    kind,
    size_bytes: typeof size === "number" && size >= 0 ? size : null,
    checksum: null,
    created_at: "",
    legacy_path: typeof runId === "string" && runId ? `${runId}/${name}` : name,
  }
}

function historyItem(value: unknown): HistoryItem | null {
  if (!value || typeof value !== "object") return null
  const item = value as Record<string, unknown>
  if (typeof item.id !== "string") return null
  const artifacts = Array.isArray(item.artifacts)
    ? item.artifacts.filter((artifact): artifact is Artifact => Boolean(artifact && typeof artifact === "object" && typeof (artifact as Artifact).id === "string"))
    : [
      legacyArtifact(item.id, item.filename, "docx", (item.artifact_sizes as Record<string, unknown> | undefined)?.docx, item.run_id),
      legacyArtifact(item.id, item.pdf_filename, "pdf", (item.artifact_sizes as Record<string, unknown> | undefined)?.pdf, item.run_id),
    ].filter((artifact): artifact is Artifact => artifact !== null)
  return {
    id: item.id,
    topic: typeof item.topic === "string" ? item.topic : "Без названия",
    status: typeof item.status === "string" ? item.status.toLowerCase() : "unknown",
    created_at: typeof item.created_at === "string" ? item.created_at : typeof item.timestamp === "string" ? item.timestamp : new Date(0).toISOString(),
    updated_at: typeof item.updated_at === "string" ? item.updated_at : typeof item.timestamp === "string" ? item.timestamp : new Date(0).toISOString(),
    archived_at: typeof item.archived_at === "string" ? item.archived_at : null,
    artifacts,
    legacy: !Array.isArray(item.artifacts),
  }
}

function historyPage(value: unknown): HistoryPage {
  const rawItems = Array.isArray(value) ? value : value && typeof value === "object" && Array.isArray((value as { items?: unknown }).items) ? (value as { items: unknown[] }).items : []
  return {
    items: rawItems.map(historyItem).filter((item): item is HistoryItem => item !== null),
    next_cursor: !Array.isArray(value) && value && typeof value === "object" && typeof (value as { next_cursor?: unknown }).next_cursor === "string" ? (value as { next_cursor: string }).next_cursor : null,
  }
}

export function HistoryWorkspace() {
  const [items, setItems] = useState<HistoryItem[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [status, setStatus] = useState("all")
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<HistoryItem | null>(null)
  const [pending, setPending] = useState<{ item: HistoryItem; action: "archive" | "delete" } | null>(null)

  const load = useCallback(async (next?: string | null, reset = false) => {
    next ? setLoadingMore(true) : setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams({ limit: "25", archived: "false" })
      if (status !== "all") params.set("status", status)
      if (next) params.set("cursor", next)
      const page = historyPage(await api<unknown>(`/api/history?${params}`))
      setItems(previous => reset || !next ? page.items : [...previous, ...page.items])
      setCursor(page.next_cursor)
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Не удалось загрузить историю.") }
    finally { setLoading(false); setLoadingMore(false) }
  }, [status])

  useEffect(() => { void load(null, true) }, [load])

  async function openDetails(id: string) {
    const listed = items.find(item => item.id === id)
    if (listed?.legacy) { setSelected(listed); return }
    try { setSelected(historyItem(await api<unknown>(`/api/history/${encodeURIComponent(id)}`)) ?? listed ?? null) }
    catch (cause) { toast.error(cause instanceof Error ? cause.message : "Работа недоступна.") }
  }
  async function download(artifact: Artifact) {
    if (artifact.id.startsWith("legacy:")) {
      window.location.assign(`/api/legacy-download?filename=${encodeURIComponent(artifact.legacy_path || artifact.name)}`)
      return
    }
    try {
      const result = await api<{ url: string; expires_at: string }>(`/api/artifacts/${encodeURIComponent(artifact.id)}/download`, { method: "POST" })
      window.location.assign(result.url)
    } catch (cause) {
      const err = cause as Error & { status?: number }
      toast.error(err.status === 410 ? "Ссылка на файл истекла. Запросите новую." : err.message)
    }
  }
  async function confirm() {
    if (!pending) return
    const { item, action } = pending
    try {
      await api(`/api/history/${encodeURIComponent(item.id)}${action === "archive" ? "/archive" : ""}`, { method: action === "archive" ? "POST" : "DELETE" })
      setItems(previous => previous.filter(candidate => candidate.id !== item.id))
      setSelected(current => current?.id === item.id ? null : current)
      toast.success(action === "archive" ? "Работа перенесена в архив." : "Работа и её файлы удалены.")
    } catch (cause) { toast.error(cause instanceof Error ? cause.message : "Не удалось обновить работу.") }
    finally { setPending(null) }
  }

  return <section className="mx-auto max-w-6xl space-y-6">
    <div><p className="text-sm text-muted-foreground">Рабочее пространство</p><h1 className="text-3xl font-bold tracking-tight">История и файлы</h1><p className="mt-2 text-sm text-muted-foreground">Недавние задания и их защищённые артефакты.</p></div>
    <div className="flex flex-wrap items-center gap-3"><Select value={status} onValueChange={setStatus}><SelectTrigger className="w-48"><SelectValue placeholder="Статус" /></SelectTrigger><SelectContent><SelectItem value="all">Все статусы</SelectItem><SelectItem value="succeeded">Готово</SelectItem><SelectItem value="failed">Ошибка</SelectItem><SelectItem value="cancelled">Отменено</SelectItem></SelectContent></Select><Button variant="outline" size="sm" onClick={() => void load(null, true)}><RefreshCw />Обновить</Button></div>
    {error && <div className="flex items-center gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"><CircleAlert className="size-4" />{error}</div>}
    {loading ? <Card><CardContent className="flex items-center justify-center gap-2 py-14 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" />Загрузка истории…</CardContent></Card> : items.length === 0 ? <Card><CardContent className="py-14 text-center"><FileText className="mx-auto size-8 text-muted-foreground" /><p className="mt-3 font-medium">История пока пуста</p><p className="mt-1 text-sm text-muted-foreground">Завершённые задания и их файлы появятся здесь.</p></CardContent></Card> : <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(20rem,.8fr)]"><div className="space-y-3">{items.map(item => <button key={item.id} onClick={() => void openDetails(item.id)} className="w-full rounded-lg border bg-card p-4 text-left hover:bg-muted/50"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="truncate font-semibold">{item.topic}</p><p className="mt-1 text-xs text-muted-foreground">{formatDate(item.created_at)} · {item.artifacts.length} файлов</p></div><span className="shrink-0 text-xs font-medium">{statusLabels[item.status] || item.status}</span></div></button>)}{cursor && <Button variant="outline" className="w-full" disabled={loadingMore} onClick={() => void load(cursor)}>{loadingMore && <Loader2 className="animate-spin" />}Показать ещё</Button>}</div><HistoryDetails item={selected} onDownload={download} onArchive={item => setPending({ item, action: "archive" })} onDelete={item => setPending({ item, action: "delete" })} /></div>}
    <AlertDialog open={Boolean(pending)} onOpenChange={open => !open && setPending(null)}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>{pending?.action === "delete" ? "Удалить работу навсегда?" : "Перенести работу в архив?"}</AlertDialogTitle><AlertDialogDescription>{pending?.action === "delete" ? "Будут удалены запись и связанные файлы. Это действие нельзя отменить." : "Работа исчезнет из недавней истории, но останется в архиве."}</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel>Отмена</AlertDialogCancel><AlertDialogAction className={pending?.action === "delete" ? "bg-destructive text-destructive-foreground hover:bg-destructive/90" : ""} onClick={() => void confirm()}>{pending?.action === "delete" ? "Удалить" : "Архивировать"}</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>
  </section>
}

function HistoryDetails({ item, onDownload, onArchive, onDelete }: { item: HistoryItem | null; onDownload: (artifact: Artifact) => void; onArchive: (item: HistoryItem) => void; onDelete: (item: HistoryItem) => void }) {
  if (!item) return <Card className="h-fit"><CardContent className="py-12 text-center text-sm text-muted-foreground">Выберите работу, чтобы увидеть её файлы.</CardContent></Card>
  return <Card className="h-fit"><CardHeader><CardTitle className="break-words">{item.topic}</CardTitle><CardDescription>{formatDate(item.created_at)} · {statusLabels[item.status] || item.status}</CardDescription></CardHeader><CardContent className="space-y-4"><div className="space-y-2">{item.artifacts.length ? item.artifacts.map(artifact => <div key={artifact.id} className="flex items-center gap-2 rounded-md border p-2"><FileText className="size-4 shrink-0 text-muted-foreground" /><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{artifact.name}</p><p className="text-xs text-muted-foreground">{artifact.kind} · {formatSize(artifact.size_bytes)}</p></div><Button variant="ghost" size="icon" aria-label={`Скачать ${artifact.name}`} onClick={() => onDownload(artifact)}><Download className="size-4" /></Button></div>) : <p className="text-sm text-muted-foreground">Для этой работы нет доступных файлов.</p>}</div><div className="flex flex-wrap gap-2 border-t pt-4">{!item.legacy && <Button asChild variant="outline" size="sm"><Link href={`/?job=${encodeURIComponent(item.id)}`}>Открыть в редакторе</Link></Button>}<Button variant="outline" size="sm" onClick={() => onArchive(item)}><Archive />Архивировать</Button><Button variant="ghost" size="sm" className="text-destructive hover:text-destructive" onClick={() => onDelete(item)}><Trash2 />Удалить</Button></div></CardContent></Card>
}
