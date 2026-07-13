"use client"

import { useCallback, useEffect, useState } from "react"
import { Activity, CircleAlert, FileWarning, Loader2, RefreshCw, ServerCog } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import {
  adminAuditPage,
  adminHealthSnapshot,
  type AdminAuditPage,
  type AdminHealthSnapshot,
} from "@/lib/admin-observability-contract"

const formatDate = (value: string) => new Intl.DateTimeFormat("ru-RU", {
  dateStyle: "medium",
  timeStyle: "medium",
}).format(new Date(value))

const severityLabel = {
  debug: "Debug",
  info: "Информация",
  warning: "Предупреждение",
  error: "Ошибка",
}

export function AdminObservability() {
  const [audit, setAudit] = useState<AdminAuditPage | null>(null)
  const [health, setHealth] = useState<AdminHealthSnapshot | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async (offset = 0) => {
    setError(null)
    try {
      const [auditResponse, healthResponse] = await Promise.all([
        fetch(`/api/admin/audit-events?limit=50&offset=${offset}`, { cache: "no-store" }),
        fetch("/api/admin/health", { cache: "no-store" }),
      ])
      if (!auditResponse.ok || !healthResponse.ok) {
        const forbidden = auditResponse.status === 403 || healthResponse.status === 403
        throw new Error(forbidden
          ? "Недостаточно прав для просмотра audit и health данных."
          : "Не удалось загрузить observability snapshot.")
      }
      const [nextAudit, nextHealth] = await Promise.all([
        auditResponse.json(),
        healthResponse.json(),
      ])
      setAudit(adminAuditPage.parse(nextAudit))
      setHealth(adminHealthSnapshot.parse(nextHealth))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Не удалось загрузить observability snapshot.")
    }
  }, [])

  useEffect(() => {
    const requestId = window.setTimeout(() => { void load() }, 0)
    return () => window.clearTimeout(requestId)
  }, [load])

  const failures = health?.telemetry.event_counts
    .filter((event) => event.severity === "error")
    .reduce((sum, event) => sum + event.count, 0) ?? 0

  return (
    <section className="space-y-6">
      <div>
        <p className="text-sm text-muted-foreground">Администрирование</p>
        <h1 className="mt-1 text-3xl font-bold tracking-tight">Аудит и здоровье</h1>
        <p className="mt-2 max-w-3xl text-muted-foreground">
          Безопасные агрегаты процессов и журнал административных действий. Содержимое metadata,
          запросов, заданий и credentials здесь не отображается.
        </p>
      </div>

      {error && (
        <Alert variant="destructive">
          <CircleAlert />
          <AlertTitle>Данные недоступны</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <MetricCard icon={Activity} title="HTTP запросы" description="С начала процесса" value={health?.telemetry.http_requests} />
        <MetricCard icon={ServerCog} title="События в буфере" description="Redacted process-local telemetry" value={health?.telemetry.events_retained} />
        <MetricCard icon={FileWarning} title="Ошибки telemetry" description="Сумма event counters с severity error" value={failures} />
      </div>

      <Card>
        <CardHeader className="flex-row items-start justify-between gap-4">
          <div>
            <CardTitle>Состояние observability</CardTitle>
            <CardDescription>Только тип, severity, outcome и счётчик — без диагностических details.</CardDescription>
          </div>
          <Button variant="outline" size="sm" onClick={() => void load()}>
            <RefreshCw />Обновить
          </Button>
        </CardHeader>
        <CardContent>
          {health === null ? (error ? null : <Loading />) : health.telemetry.event_counts.length === 0 ? (
            <p className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">В текущем процессе ещё нет telemetry событий.</p>
          ) : (
            <Table>
              <TableHeader><TableRow><TableHead>Событие</TableHead><TableHead>Severity</TableHead><TableHead>Outcome</TableHead><TableHead className="text-right">Количество</TableHead></TableRow></TableHeader>
              <TableBody>{health.telemetry.event_counts.map((event) => (
                <TableRow key={`${event.event_type}:${event.severity}:${event.outcome}`}>
                  <TableCell className="font-mono text-xs">{event.event_type}</TableCell>
                  <TableCell><Badge variant={event.severity === "error" ? "destructive" : event.severity === "warning" ? "outline" : "secondary"}>{severityLabel[event.severity]}</Badge></TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">{event.outcome}</TableCell>
                  <TableCell className="text-right font-mono">{event.count}</TableCell>
                </TableRow>
              ))}</TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-start justify-between gap-4">
          <div>
            <CardTitle>Журнал аудита</CardTitle>
            <CardDescription>События отсортированы от новых к старым; raw metadata намеренно исключены из контракта.</CardDescription>
          </div>
          <Button variant="outline" size="sm" onClick={() => void load()}>
            <RefreshCw />Обновить
          </Button>
        </CardHeader>
        <CardContent>
          {audit === null ? (error ? null : <Loading />) : audit.events.length === 0 ? (
            <p className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">Audit events пока отсутствуют.</p>
          ) : (
            <>
              <Table>
                <TableHeader><TableRow><TableHead>Событие</TableHead><TableHead>Actor</TableHead><TableHead>Correlation ID</TableHead><TableHead className="text-right">Время</TableHead></TableRow></TableHeader>
                <TableBody>{audit.events.map((event) => (
                  <TableRow key={event.id}>
                    <TableCell className="font-mono text-xs">{event.event_type}</TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">{event.actor_user_id ?? "system"}</TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">{event.correlation_id ?? "—"}</TableCell>
                    <TableCell className="text-right text-xs text-muted-foreground">{formatDate(event.created_at)}</TableCell>
                  </TableRow>
                ))}</TableBody>
              </Table>
              {audit.next_offset !== null && (
                <div className="mt-4 flex justify-center">
                  <Button variant="outline" onClick={() => void load(audit.next_offset!)}>Показать следующие события</Button>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </section>
  )
}

function MetricCard({ icon: Icon, title, description, value }: {
  icon: typeof Activity
  title: string
  description: string
  value: number | undefined
}) {
  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Icon className="size-5 text-ape-primary" />{title}</CardTitle><CardDescription>{description}</CardDescription></CardHeader>
      <CardContent>{value === undefined ? <Loading /> : <p className="text-3xl font-semibold">{value}</p>}</CardContent>
    </Card>
  )
}

function Loading() {
  return <div className="flex items-center justify-center gap-2 py-6 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" />Загружаем данные…</div>
}
