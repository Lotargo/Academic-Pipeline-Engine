"use client"

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react"
import { CheckCircle2, CircleAlert, Cloud, KeyRound, Loader2, RefreshCw, Replace, ShieldCheck, Trash2 } from "lucide-react"
import { toast } from "sonner"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import type { Availability, CredentialMetadata, CredentialPolicy, Provider, ProviderSelection, ProviderSettingsSnapshot, ValidationState } from "@/lib/provider-contract"
import { credentialMetadata, providerSettingsSnapshot } from "@/lib/provider-contract"

type ApiError = Error & { status?: number }

async function api<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, headers: { "content-type": "application/json", ...init?.headers }, cache: "no-store" })
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as { detail?: unknown }
    const error = new Error(typeof body.detail === "string" ? body.detail : "Не удалось выполнить запрос.") as ApiError
    error.status = response.status
    throw error
  }
  return response.status === 204 ? undefined as T : response.json() as Promise<T>
}

const availabilityLabel: Record<Availability, string> = { available: "Доступен", degraded: "Ограничен", exhausted: "Исчерпан", unavailable: "Недоступен" }
const validationLabel: Record<ValidationState, string> = { valid: "Проверен", invalid: "Проверка не пройдена", unknown: "Не проверен" }

function availabilityMessage(provider: Provider) {
  if (provider.availability === "exhausted") return "Платформенный ресурс исчерпан. Добавьте свой ключ, чтобы продолжить работу."
  if (provider.availability === "unavailable") return "Платформенный ресурс временно недоступен. Можно использовать свой ключ."
  if (provider.availability === "degraded") return "Платформенный ресурс работает с ограничениями; свой ключ может быть надёжнее."
  return "Платформенный ресурс доступен в best-effort режиме. Точный остаток квоты не отображается."
}

function firstSelection(snapshot: ProviderSettingsSnapshot): ProviderSelection | null {
  if (snapshot.selection) return snapshot.selection
  const provider = snapshot.providers[0]
  const model = provider?.models[0]
  return provider && model ? { provider_id: provider.id, model_id: model.id, credential_policy: "platform_first" } : null
}

function validationVariant(state: ValidationState) { return state === "invalid" ? "destructive" : state === "valid" ? "default" : "secondary" }

export function ProviderSettings() {
  const [snapshot, setSnapshot] = useState<ProviderSettingsSnapshot | null>(null)
  const [selection, setSelection] = useState<ProviderSelection | null>(null)
  const [loading, setLoading] = useState(true)
  const [savingSelection, setSavingSelection] = useState(false)
  const [adding, setAdding] = useState(false)
  const [replacing, setReplacing] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<CredentialMetadata | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [newProvider, setNewProvider] = useState("")
  const [newLabel, setNewLabel] = useState("")
  const [newSecret, setNewSecret] = useState("")
  const [replacementSecret, setReplacementSecret] = useState("")

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const next = providerSettingsSnapshot(await api<unknown>("/api/provider-settings"))
      setSnapshot(next)
      setSelection(firstSelection(next))
      setNewProvider(current => current || next.providers[0]?.id || "")
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Не удалось загрузить настройки провайдеров.") }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { void load() }, [load])

  const selectedProvider = useMemo(() => snapshot?.providers.find(provider => provider.id === selection?.provider_id) ?? null, [snapshot, selection])
  const activeCredential = Boolean(selectedProvider && snapshot?.credentials.some(credential => credential.provider_id === selectedProvider.id && credential.status === "active"))

  function selectProvider(providerId: string) {
    const provider = snapshot?.providers.find(item => item.id === providerId)
    setSelection(current => provider && provider.models[0] ? { provider_id: provider.id, model_id: provider.models.some(model => model.id === current?.model_id) ? current!.model_id : provider.models[0].id, credential_policy: current?.credential_policy ?? "platform_first" } : null)
  }

  async function saveSelection() {
    if (!selection) return
    if (selection.credential_policy === "user_only" && !activeCredential) { toast.error("Сначала добавьте активный ключ выбранного провайдера."); return }
    setSavingSelection(true)
    try {
      const saved = await api<unknown>("/api/provider-settings", { method: "PUT", body: JSON.stringify(selection) })
      const parsed = providerSettingsSnapshot({ providers: snapshot?.providers ?? [], credentials: snapshot?.credentials ?? [], selection: saved })
      setSelection(parsed.selection ?? selection)
      toast.success("Настройки провайдера сохранены.")
    } catch (cause) { toast.error(cause instanceof Error ? cause.message : "Не удалось сохранить выбор.") }
    finally { setSavingSelection(false) }
  }

  async function addCredential(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!newProvider || !newSecret.trim()) return
    setAdding(true)
    try {
      const result = credentialMetadata(await api<unknown>("/api/credentials", { method: "POST", body: JSON.stringify({ provider_id: newProvider, label: newLabel.trim() || "Основной ключ", secret: newSecret }) }))
      if (!result) throw new Error("Сервис вернул некорректные metadata ключа.")
      setSnapshot(current => current ? { ...current, credentials: [...current.credentials, result] } : current)
      setNewLabel(""); setNewSecret("")
      toast.success("Ключ сохранён. Его значение больше не показывается.")
    } catch (cause) { toast.error(cause instanceof Error ? cause.message : "Не удалось сохранить ключ.") }
    finally { setAdding(false) }
  }

  async function replaceCredential(event: FormEvent<HTMLFormElement>, credential: CredentialMetadata) {
    event.preventDefault()
    if (!replacementSecret.trim()) return
    setReplacing(credential.id)
    try {
      const result = credentialMetadata(await api<unknown>(`/api/credentials/${encodeURIComponent(credential.id)}`, { method: "PATCH", body: JSON.stringify({ secret: replacementSecret }) }))
      if (!result) throw new Error("Сервис вернул некорректные metadata ключа.")
      setSnapshot(current => current ? { ...current, credentials: current.credentials.map(item => item.id === result.id ? result : item) } : current)
      setReplacing(null); setReplacementSecret("")
      toast.success("Ключ заменён. Предыдущее значение отозвано.")
    } catch (cause) { toast.error(cause instanceof Error ? cause.message : "Не удалось заменить ключ.") }
    finally { setReplacing(current => current === credential.id ? null : current) }
  }

  async function deleteCredential() {
    if (!deleting) return
    try {
      await api(`/api/credentials/${encodeURIComponent(deleting.id)}`, { method: "DELETE" })
      setSnapshot(current => current ? { ...current, credentials: current.credentials.filter(credential => credential.id !== deleting.id) } : current)
      toast.success("Ключ удалён.")
    } catch (cause) { toast.error(cause instanceof Error ? cause.message : "Не удалось удалить ключ.") }
    finally { setDeleting(null) }
  }

  if (loading) return <Card><CardContent className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" />Загружаем настройки провайдеров…</CardContent></Card>
  if (!snapshot) return <Unavailable error={error} onRetry={load} />

  return <section className="mx-auto max-w-5xl space-y-6">
    <div><p className="text-sm text-muted-foreground">Рабочее пространство</p><h1 className="text-3xl font-bold tracking-tight">Провайдеры и API-ключи</h1><p className="mt-2 text-sm text-muted-foreground">Выберите модель, используйте общий ресурс платформы или подключите собственный ключ.</p></div>
    {error && <Alert variant="destructive"><CircleAlert /><AlertTitle>Не удалось обновить настройки</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}
    {snapshot.providers.length === 0 ? <Unavailable error="Сервис ещё не передал список доступных провайдеров." onRetry={load} /> : <>
      <Card><CardHeader><CardTitle className="flex items-center gap-2"><Cloud className="size-5 text-ape-primary" />Выбор провайдера</CardTitle><CardDescription>Модель используется для новых заданий. Платформенные ресурсы предоставляются без платных статусов и без отображения точных квот.</CardDescription></CardHeader><CardContent className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2"><div className="space-y-2"><Label htmlFor="provider">Провайдер</Label><Select value={selection?.provider_id ?? ""} onValueChange={selectProvider}><SelectTrigger id="provider"><SelectValue placeholder="Выберите провайдера" /></SelectTrigger><SelectContent>{snapshot.providers.map(provider => <SelectItem key={provider.id} value={provider.id}>{provider.display_name}</SelectItem>)}</SelectContent></Select></div><div className="space-y-2"><Label htmlFor="model">Модель</Label><Select value={selection?.model_id ?? ""} onValueChange={modelId => setSelection(current => current ? { ...current, model_id: modelId } : current)} disabled={!selectedProvider?.models.length}><SelectTrigger id="model"><SelectValue placeholder="Выберите модель" /></SelectTrigger><SelectContent>{selectedProvider?.models.map(model => <SelectItem key={model.id} value={model.id}>{model.id}{model.capabilities.length ? ` · ${model.capabilities.join(", ")}` : ""}</SelectItem>)}</SelectContent></Select></div></div>
        {selectedProvider && <Alert><Cloud /><AlertTitle>{availabilityLabel[selectedProvider.availability]}</AlertTitle><AlertDescription>{availabilityMessage(selectedProvider)}</AlertDescription></Alert>}
        <div className="space-y-3 rounded-lg border p-4"><p className="text-sm font-medium">Источник ключа</p><label className="flex cursor-pointer items-start gap-3 rounded-md border p-3 has-[:checked]:border-ape-primary has-[:checked]:bg-ape-primary-soft/40"><input type="radio" name="credential-policy" checked={selection?.credential_policy === "platform_first"} onChange={() => setSelection(current => current ? { ...current, credential_policy: "platform_first" } : current)} /><span><span className="block text-sm font-medium">Ресурс платформы с BYOK fallback</span><span className="text-xs text-muted-foreground">Сначала используется доступный общий ресурс; ваш ключ может быть задействован только по выбранной политике backend.</span></span></label><label className="flex cursor-pointer items-start gap-3 rounded-md border p-3 has-[:checked]:border-ape-primary has-[:checked]:bg-ape-primary-soft/40"><input type="radio" name="credential-policy" checked={selection?.credential_policy === "user_only"} onChange={() => setSelection(current => current ? { ...current, credential_policy: "user_only" } : current)} disabled={!activeCredential} /><span><span className="block text-sm font-medium">Только мой ключ</span><span className="text-xs text-muted-foreground">{activeCredential ? "Используется активный ключ выбранного провайдера." : "Добавьте активный ключ выбранного провайдера, чтобы включить этот режим."}</span></span></label></div>
        <Button onClick={() => void saveSelection()} disabled={!selection || savingSelection}>{savingSelection && <Loader2 className="animate-spin" />}Сохранить выбор</Button>
      </CardContent></Card>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,.75fr)]"><CredentialList credentials={snapshot.credentials} providers={snapshot.providers} replacing={replacing} onReplacing={setReplacing} replacementSecret={replacementSecret} onReplacementSecret={setReplacementSecret} onReplace={replaceCredential} onDelete={setDeleting} /><Card className="h-fit"><CardHeader><CardTitle className="flex items-center gap-2"><KeyRound className="size-5 text-ape-primary" />Добавить свой ключ</CardTitle><CardDescription>Значение передаётся только для сохранения и после этого не возвращается в интерфейс.</CardDescription></CardHeader><CardContent><form className="space-y-4" onSubmit={addCredential}><div className="space-y-2"><Label htmlFor="credential-provider">Провайдер</Label><Select value={newProvider} onValueChange={setNewProvider}><SelectTrigger id="credential-provider"><SelectValue placeholder="Выберите провайдера" /></SelectTrigger><SelectContent>{snapshot.providers.filter(provider => provider.supports_byok).map(provider => <SelectItem key={provider.id} value={provider.id}>{provider.display_name}</SelectItem>)}</SelectContent></Select></div><div className="space-y-2"><Label htmlFor="credential-label">Метка</Label><Input id="credential-label" value={newLabel} onChange={event => setNewLabel(event.target.value)} maxLength={200} placeholder="Например, рабочий ключ" /></div><div className="space-y-2"><Label htmlFor="credential-secret">API-ключ</Label><Input id="credential-secret" type="password" autoComplete="new-password" value={newSecret} onChange={event => setNewSecret(event.target.value)} placeholder="Вставьте новый ключ" required /><p className="text-xs text-muted-foreground">Ключ не сохраняется в localStorage и не отображается после отправки.</p></div><Button type="submit" disabled={adding || !newProvider || !newSecret.trim()}>{adding && <Loader2 className="animate-spin" />}Сохранить ключ</Button></form></CardContent></Card></div>
    </>}
    <AlertDialog open={Boolean(deleting)} onOpenChange={open => !open && setDeleting(null)}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>Удалить ключ?</AlertDialogTitle><AlertDialogDescription>Ключ «{deleting?.label}» будет отозван и удалён. Это действие нельзя отменить.</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel>Отмена</AlertDialogCancel><AlertDialogAction className="bg-destructive text-destructive-foreground hover:bg-destructive/90" onClick={() => void deleteCredential()}>Удалить ключ</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>
  </section>
}

function CredentialList({ credentials, providers, replacing, onReplacing, replacementSecret, onReplacementSecret, onReplace, onDelete }: { credentials: CredentialMetadata[]; providers: Provider[]; replacing: string | null; onReplacing: (id: string | null) => void; replacementSecret: string; onReplacementSecret: (value: string) => void; onReplace: (event: FormEvent<HTMLFormElement>, credential: CredentialMetadata) => Promise<void>; onDelete: (credential: CredentialMetadata) => void }) {
  const providerName = (id: string) => providers.find(provider => provider.id === id)?.display_name || id
  return <Card><CardHeader><CardTitle className="flex items-center gap-2"><ShieldCheck className="size-5 text-ape-primary" />Сохранённые ключи</CardTitle><CardDescription>Показываются только безопасные metadata. Полное значение ключа недоступно даже после сохранения.</CardDescription></CardHeader><CardContent className="space-y-3">{credentials.length === 0 ? <p className="rounded-md border border-dashed p-5 text-sm text-muted-foreground">Собственных ключей пока нет.</p> : credentials.filter(credential => credential.status !== "deleted").map(credential => <div key={credential.id} className="rounded-lg border p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-medium">{credential.label}</p><p className="mt-1 text-xs text-muted-foreground">{providerName(credential.provider_id)} · {credential.masked_value}</p></div><div className="flex items-center gap-2"><Badge variant={validationVariant(credential.validation)}>{credential.validation === "valid" && <CheckCircle2 />}{validationLabel[credential.validation]}</Badge><Badge variant={credential.status === "active" ? "secondary" : "outline"}>{credential.status === "active" ? "Активен" : "Отключён"}</Badge></div></div><div className="mt-3 flex flex-wrap gap-2"><Button variant="outline" size="sm" onClick={() => { const opens = replacing !== credential.id; onReplacing(opens ? credential.id : null); onReplacementSecret(""); if (opens) window.requestAnimationFrame(() => document.getElementById(`replace-${credential.id}`)?.focus()) }}><Replace />{replacing === credential.id ? "Отменить замену" : "Заменить"}</Button><Button variant="ghost" size="sm" className="text-destructive hover:text-destructive" onClick={() => onDelete(credential)}><Trash2 />Удалить</Button></div>{replacing === credential.id && <form className="mt-3 flex flex-wrap gap-2 border-t pt-3" onSubmit={event => void onReplace(event, credential)}><Label htmlFor={`replace-${credential.id}`} className="sr-only">Новый API-ключ</Label><Input id={`replace-${credential.id}`} className="max-w-sm" type="password" autoComplete="new-password" value={replacementSecret} onChange={event => onReplacementSecret(event.target.value)} placeholder="Новый API-ключ" required /><Button type="submit" disabled={!replacementSecret.trim()}>Сохранить замену</Button></form>}</div>)}</CardContent></Card>
}

function Unavailable({ error, onRetry }: { error: string | null; onRetry: () => Promise<void> }) {
  return <Card><CardContent className="py-12 text-center"><CircleAlert className="mx-auto size-8 text-muted-foreground" /><p className="mt-3 font-medium">Настройки пока недоступны</p><p className="mx-auto mt-2 max-w-lg text-sm text-muted-foreground">{error || "Проверьте подключение к сервису и повторите попытку."}</p><Button className="mt-5" variant="outline" onClick={() => void onRetry()}><RefreshCw />Повторить</Button></CardContent></Card>
}
