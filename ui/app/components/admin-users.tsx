"use client"

import { useCallback, useEffect, useState } from "react"
import { CircleAlert, Loader2, RefreshCw, ShieldCheck, UsersRound } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { adminUsers, type AdminUser } from "@/lib/admin-contract"

const roleLabel = { user: "Пользователь", admin: "Администратор", service: "Сервис" }
const statusLabel = { active: "Активен", blocked: "Заблокирован", deleted: "Удалён" }

export function AdminUsers() {
  const [users, setUsers] = useState<AdminUser[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setError(null)
    try {
      const response = await fetch("/api/admin/users", { cache: "no-store" })
      if (!response.ok) {
        const body = await response.json().catch(() => ({})) as { detail?: string }
        throw new Error(response.status === 403 ? "Недостаточно прав для просмотра пользователей." : body.detail || "Не удалось загрузить пользователей.")
      }
      setUsers(adminUsers(await response.json()))
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Не удалось загрузить пользователей.") }
  }, [])

  useEffect(() => {
    const requestId = window.setTimeout(() => { void load() }, 0)
    return () => window.clearTimeout(requestId)
  }, [load])

  return <section className="space-y-6"><div><p className="text-sm text-muted-foreground">Администрирование</p><h1 className="mt-1 text-3xl font-bold tracking-tight">Пользователи и роли</h1><p className="mt-2 text-muted-foreground">Роли администратора выдаются только одноразовыми invite-токенами. Пароли, сессии и другие секреты здесь не отображаются.</p></div>{error && <Alert variant="destructive"><CircleAlert /><AlertTitle>Данные недоступны</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}<Card><CardHeader className="flex-row items-start justify-between gap-4"><div><CardTitle className="flex items-center gap-2"><UsersRound className="size-5 text-ape-primary" />Учётные записи</CardTitle><CardDescription>Доступные для администратора безопасные metadata.</CardDescription></div><Button variant="outline" size="sm" onClick={() => void load()}><RefreshCw />Обновить</Button></CardHeader><CardContent>{users === null && !error ? <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" />Загружаем пользователей…</div> : <Table><TableHeader><TableRow><TableHead>Email</TableHead><TableHead>Роль</TableHead><TableHead>Статус</TableHead><TableHead className="text-right">Создан</TableHead></TableRow></TableHeader><TableBody>{users?.map(user => <TableRow key={user.id}><TableCell><p className="font-medium">{user.email}</p><p className="font-mono text-xs text-muted-foreground">{user.id}</p></TableCell><TableCell><Badge variant={user.role === "admin" ? "default" : "secondary"}>{user.role === "admin" && <ShieldCheck />}{roleLabel[user.role]}</Badge></TableCell><TableCell><Badge variant={user.status === "active" ? "outline" : "destructive"}>{statusLabel[user.status]}</Badge></TableCell><TableCell className="text-right text-muted-foreground">{new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium" }).format(new Date(user.created_at))}</TableCell></TableRow>)}</TableBody></Table>}</CardContent></Card></section>
}
