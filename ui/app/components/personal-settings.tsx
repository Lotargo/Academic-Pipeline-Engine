"use client"

import { FormEvent, useEffect, useState } from "react"
import { CircleAlert, Loader2, Save, SlidersHorizontal, UserRound } from "lucide-react"
import { useTheme } from "next-themes"
import { toast } from "sonner"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { parsePersonalSettings, type PersonalSettingsSnapshot } from "@/lib/personal-settings"

type Draft = PersonalSettingsSnapshot["profile"] & PersonalSettingsSnapshot["editor_defaults"]

const artifactOptions = [
  { value: "auto", label: "Определять автоматически" },
  { value: "academic_paper", label: "Академическая статья" },
  { value: "report", label: "Отчёт" },
  { value: "technical_readme", label: "Технический README" },
  { value: "plan_document", label: "План документа" },
  { value: "unknown_freeform", label: "Свободный формат" },
]

const toDraft = (snapshot: PersonalSettingsSnapshot): Draft => ({
  ...snapshot.profile,
  ...snapshot.editor_defaults,
  artifact_override: snapshot.editor_defaults.artifact_override ?? "auto",
})

export function PersonalSettings() {
  const { setTheme } = useTheme()
  const [snapshot, setSnapshot] = useState<PersonalSettingsSnapshot | null>(null)
  const [draft, setDraft] = useState<Draft | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    void fetch("/api/settings/me", { cache: "no-store" })
      .then(async response => {
        const body = await response.json().catch(() => null)
        if (!response.ok) throw new Error(typeof body?.detail === "string" ? body.detail : "Не удалось загрузить личные настройки.")
        const parsed = parsePersonalSettings(body)
        if (!parsed) throw new Error("Сервис вернул неполные личные настройки.")
        return parsed
      })
      .then(next => {
        if (!active) return
        setSnapshot(next)
        setDraft(toDraft(next))
      })
      .catch(cause => active && setError(cause instanceof Error ? cause.message : "Не удалось загрузить личные настройки."))
      .finally(() => active && setLoading(false))
    return () => { active = false }
  }, [])

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!draft) return
    setSaving(true)
    setError(null)
    try {
      const response = await fetch("/api/settings/me", {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          display_name: draft.display_name?.trim() || null,
          language: draft.language,
          theme: draft.theme,
          editor_defaults: {
            academic_mode: Boolean(draft.academic_mode),
            web_search_enabled: Boolean(draft.web_search_enabled),
            author: draft.author?.trim() || null,
            artifact_override: draft.artifact_override === "auto" ? null : draft.artifact_override ?? null,
          },
        }),
      })
      const body = await response.json().catch(() => null)
      if (!response.ok) throw new Error(typeof body?.detail === "string" ? body.detail : "Не удалось сохранить настройки.")
      const next = parsePersonalSettings(body)
      if (!next) throw new Error("Сервис вернул неполные личные настройки.")
      setSnapshot(next)
      setDraft(toDraft(next))
      setTheme(next.profile.theme)
      toast.success("Личные настройки сохранены.")
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "Не удалось сохранить настройки."
      setError(message)
      toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <Card><CardContent className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" />Загружаем личные настройки…</CardContent></Card>
  if (!snapshot || !draft) return <Alert variant="destructive"><CircleAlert /><AlertTitle>Настройки недоступны</AlertTitle><AlertDescription>{error ?? "Не удалось определить текущий workspace."}</AlertDescription></Alert>

  return <section className="space-y-6">
    <div>
      <p className="text-sm text-muted-foreground">Личный кабинет · {snapshot.workspace.name}</p>
      <h1 className="mt-1 text-3xl font-bold tracking-tight">Личные настройки</h1>
      <p className="mt-2 max-w-3xl text-sm text-muted-foreground">Профиль принадлежит только вашей учётной записи. Значения редактора и выбор провайдера сохраняются отдельно для вас в текущем workspace — они не меняют сервер и не переписывают настройки других участников.</p>
    </div>
    {error && <Alert variant="destructive"><CircleAlert /><AlertTitle>Не удалось сохранить изменения</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}
    <form className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(20rem,.78fr)]" onSubmit={save}>
      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><UserRound className="size-5 text-ape-primary" />Профиль и интерфейс</CardTitle><CardDescription>Эти сведения видны только в вашем интерфейсе и не используются как server-wide configuration.</CardDescription></CardHeader>
        <CardContent className="grid gap-5 sm:grid-cols-2">
          <div className="space-y-2 sm:col-span-2"><Label htmlFor="settings-display-name">Отображаемое имя</Label><Input id="settings-display-name" value={draft.display_name ?? ""} onChange={event => setDraft(current => current ? { ...current, display_name: event.target.value } : current)} maxLength={120} placeholder="Как к вам обращаться" /></div>
          <div className="space-y-2"><Label htmlFor="settings-language">Язык</Label><Select value={draft.language} onValueChange={language => setDraft(current => current ? { ...current, language: language === "en" ? "en" : "ru" } : current)}><SelectTrigger id="settings-language"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="ru">Русский</SelectItem><SelectItem value="en">English</SelectItem></SelectContent></Select></div>
          <div className="space-y-2"><Label htmlFor="settings-theme">Тема</Label><Select value={draft.theme} onValueChange={theme => setDraft(current => current ? { ...current, theme: theme as Draft["theme"] } : current)}><SelectTrigger id="settings-theme"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="system">Системная</SelectItem><SelectItem value="dark">Тёмная</SelectItem><SelectItem value="light">Светлая</SelectItem></SelectContent></Select></div>
        </CardContent>
      </Card>
      <Card className="h-fit border-ape-primary/25 bg-ape-primary-soft/20"><CardHeader><CardTitle className="text-lg">Граница данных</CardTitle><CardDescription>Текущий workspace: {snapshot.workspace.name}.</CardDescription></CardHeader><CardContent className="space-y-3 text-sm text-muted-foreground"><p>Профиль: только ваша учётная запись.</p><p>Параметры редактора и ключи: только вы в этом workspace.</p><p>Настройки агентов, серверные secrets и общие квоты здесь намеренно недоступны.</p></CardContent></Card>
      <Card className="xl:col-span-2">
        <CardHeader><CardTitle className="flex items-center gap-2"><SlidersHorizontal className="size-5 text-ape-primary" />Значения по умолчанию для новых заданий</CardTitle><CardDescription>Редактор подставляет их только в новые задания. Каждое значение можно изменить перед запуском, а уже созданные jobs не меняются.</CardDescription></CardHeader>
        <CardContent className="grid gap-5 md:grid-cols-2">
          <div className="space-y-2"><Label htmlFor="settings-author">Автор</Label><Input id="settings-author" value={draft.author ?? ""} onChange={event => setDraft(current => current ? { ...current, author: event.target.value } : current)} maxLength={200} placeholder="Например, имя автора" /></div>
          <div className="space-y-2"><Label htmlFor="settings-artifact">Предпочтительный формат</Label><Select value={draft.artifact_override ?? "auto"} onValueChange={artifact_override => setDraft(current => current ? { ...current, artifact_override } : current)}><SelectTrigger id="settings-artifact"><SelectValue /></SelectTrigger><SelectContent>{artifactOptions.map(option => <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>)}</SelectContent></Select></div>
          <div className="flex items-start justify-between gap-4 rounded-lg border p-4"><div><Label htmlFor="settings-academic">Академический режим</Label><p className="mt-1 text-xs text-muted-foreground">Подставлять академический режим для новых заданий.</p></div><Switch id="settings-academic" checked={Boolean(draft.academic_mode)} onCheckedChange={academic_mode => setDraft(current => current ? { ...current, academic_mode } : current)} /></div>
          <div className="flex items-start justify-between gap-4 rounded-lg border p-4"><div><Label htmlFor="settings-web-search">Веб-поиск</Label><p className="mt-1 text-xs text-muted-foreground">Подставлять поиск источников, если он доступен выбранному pipeline.</p></div><Switch id="settings-web-search" checked={Boolean(draft.web_search_enabled)} onCheckedChange={web_search_enabled => setDraft(current => current ? { ...current, web_search_enabled } : current)} /></div>
        </CardContent>
      </Card>
      <div className="xl:col-span-2 flex justify-end"><Button type="submit" disabled={saving}>{saving ? <Loader2 className="animate-spin" /> : <Save />}Сохранить личные настройки</Button></div>
    </form>
  </section>
}
