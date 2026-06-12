"use client"

import { useEffect, useMemo, useState } from "react"
import { ArchiveRestore, FileText, Loader2 } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import type { UiLanguage } from "@/lib/i18n"

interface ArchivedWorksModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  language: UiLanguage
  onRestored: () => void
}

const labels = {
  en: {
    title: "Archived works",
    description: "Review hidden works and restore them to the recent list.",
    empty: "No archived works yet.",
    loading: "Loading archived works...",
    error: "Failed to load archived works",
    restoreSelected: "Restore selected",
    restoring: "Restoring...",
    selected: "selected",
    author: "Author",
    template: "Template",
    language: "Language",
    status: "Status",
    timestamp: "Created",
    exportFile: "Export",
    restored: "Archived works restored",
  },
  ru: {
    title: "Архивные работы",
    description: "Просмотр скрытых работ и возврат в список последних.",
    empty: "Архивных работ пока нет.",
    loading: "Загрузка архива...",
    error: "Не удалось загрузить архив",
    restoreSelected: "Восстановить выбранные",
    restoring: "Восстановление...",
    selected: "выбрано",
    author: "Автор",
    template: "Шаблон",
    language: "Язык",
    status: "Статус",
    timestamp: "Создано",
    exportFile: "Экспорт",
    restored: "Работы восстановлены",
  },
} as const

export function ArchivedWorksModal({ open, onOpenChange, language, onRestored }: ArchivedWorksModalProps) {
  const [items, setItems] = useState<any[]>([])
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [restoring, setRestoring] = useState(false)
  const t = labels[language]

  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds])

  const loadArchived = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch("/api/history?archived=true")
      if (!res.ok) throw new Error(t.error)
      const data = await res.json()
      setItems(data)
      setSelectedIds((ids) => ids.filter((id) => data.some((item: any) => item.id === id)))
    } catch (e: any) {
      setError(e.message || t.error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (open) loadArchived()
  }, [open])

  const toggleSelected = (id: string) => {
    setSelectedIds((ids) => (ids.includes(id) ? ids.filter((item) => item !== id) : [...ids, id]))
  }

  const restoreSelected = async () => {
    if (selectedIds.length === 0) return
    setRestoring(true)
    try {
      const res = await fetch("/api/history/unarchive", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids: selectedIds }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || t.error)
      }
      toast.success(t.restored)
      setSelectedIds([])
      await loadArchived()
      onRestored()
    } catch (e: any) {
      toast.error(e.message || t.error)
    } finally {
      setRestoring(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-hidden sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>{t.title}</DialogTitle>
          <DialogDescription>{t.description}</DialogDescription>
        </DialogHeader>

        <div className="flex items-center justify-between gap-3 border-b pb-3">
          <span className="text-xs text-muted-foreground">
            {selectedIds.length} {t.selected}
          </span>
          <Button size="sm" onClick={restoreSelected} disabled={selectedIds.length === 0 || restoring}>
            {restoring ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ArchiveRestore className="h-3.5 w-3.5" />}
            {restoring ? t.restoring : t.restoreSelected}
          </Button>
        </div>

        <div className="max-h-[55vh] overflow-y-auto pr-1">
          {loading && (
            <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              {t.loading}
            </div>
          )}

          {!loading && error && (
            <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
              {error}
            </div>
          )}

          {!loading && !error && items.length === 0 && (
            <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
              {t.empty}
            </div>
          )}

          {!loading && !error && items.length > 0 && (
            <div className="space-y-2">
              {items.map((item) => (
                <div key={item.id} className="flex gap-3 rounded-lg border p-3">
                  <Checkbox checked={selectedSet.has(item.id)} onCheckedChange={() => toggleSelected(item.id)} />
                  <FileText className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                  <div className="min-w-0 flex-1 space-y-2">
                    <div>
                      <h3 className="truncate text-sm font-semibold">{item.topic || "Untitled"}</h3>
                      <p className="text-xs text-muted-foreground">{item.timestamp || "-"}</p>
                    </div>
                    <div className="grid gap-1 text-xs text-muted-foreground sm:grid-cols-2">
                      <span>{t.author}: {item.author || "-"}</span>
                      <span>{t.template}: {item.template_id || item.template_mode || "-"}</span>
                      <span>{t.language}: {item.runtime_template?.language_policy || "-"}</span>
                      <span>{t.status}: {item.status || "-"}</span>
                      <span>{t.exportFile}: {item.filename || "-"}</span>
                      <span>{t.timestamp}: {item.timestamp || "-"}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
