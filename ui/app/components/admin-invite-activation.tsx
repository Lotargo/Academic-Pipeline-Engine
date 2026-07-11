"use client"

import { FormEvent, useState } from "react"
import { useRouter } from "next/navigation"
import { BadgeCheck, KeyRound, Loader2 } from "lucide-react"
import { toast } from "sonner"
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

export function AdminInviteActivation() {
  const router = useRouter()
  const [token, setToken] = useState("")
  const [confirming, setConfirming] = useState(false)
  const [pending, setPending] = useState(false)
  const usable = token.trim().length >= 32

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (usable) setConfirming(true)
  }

  async function activate() {
    setPending(true)
    try {
      const response = await fetch("/api/admin-invites/activate", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ invite_token: token.trim() }),
      })
      if (!response.ok) {
        const body = await response.json().catch(() => ({})) as { detail?: unknown }
        throw new Error(typeof body.detail === "string" ? body.detail : "Не удалось активировать приглашение.")
      }
      setToken("")
      toast.success("Роль администратора активирована. Войдите снова.")
      router.replace("/login?reason=admin_activated")
      router.refresh()
    } catch (cause) {
      toast.error(cause instanceof Error ? cause.message : "Не удалось активировать приглашение.")
    } finally {
      setPending(false)
      setConfirming(false)
    }
  }

  return <>
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><BadgeCheck className="size-5 text-ape-primary" />Приглашение администратора</CardTitle>
        <CardDescription>Если оператор платформы передал одноразовый токен, активируйте его в своей уже открытой учётной записи.</CardDescription>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" onSubmit={submit} noValidate>
          <div className="space-y-2">
            <Label htmlFor="admin-invite-token">Одноразовый токен</Label>
            <Input id="admin-invite-token" type="password" autoComplete="off" value={token} onChange={event => setToken(event.target.value)} placeholder="Вставьте токен приглашения" minLength={32} maxLength={1024} required disabled={pending} />
            <p className="text-xs text-muted-foreground">Токен передаётся только для активации, не сохраняется в интерфейсе и после использования становится недействительным.</p>
          </div>
          <Button type="submit" disabled={!usable || pending}><KeyRound />Активировать роль</Button>
        </form>
      </CardContent>
    </Card>
    <AlertDialog open={confirming} onOpenChange={open => !pending && setConfirming(open)}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Активировать роль администратора?</AlertDialogTitle>
          <AlertDialogDescription>Роль будет повышена для текущей учётной записи. Токен можно использовать только один раз; текущая сессия завершится, и потребуется войти снова.</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={pending}>Отмена</AlertDialogCancel>
          <AlertDialogAction onClick={() => void activate()} disabled={pending}>{pending && <Loader2 className="animate-spin" />}Активировать</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </>
}
