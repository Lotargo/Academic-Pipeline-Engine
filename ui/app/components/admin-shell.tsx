"use client"

import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { useState } from "react"
import { Activity, Bot, ClipboardList, Gauge, LayoutDashboard, LogOut, Menu, ShieldCheck, UsersRound, X } from "lucide-react"
import { AcademicLogoIcon } from "@/app/components/academic-logo-icon"
import { useCabinetSession } from "@/app/components/session-gate"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"

const navigation = [
  { href: "/admin", label: "Обзор", icon: LayoutDashboard },
  { href: "/admin/users", label: "Пользователи", icon: UsersRound },
  { href: "/admin/resources", label: "Ресурсы", icon: Bot },
  { href: "/admin/jobs", label: "Очереди и задания", icon: ClipboardList },
  { href: "/admin/audit", label: "Аудит и здоровье", icon: Activity },
]

export function AdminShell({ children }: { children: React.ReactNode }) {
  const session = useCabinetSession()
  const pathname = usePathname()
  const router = useRouter()
  const [menuOpen, setMenuOpen] = useState(false)
  const initials = session?.email.slice(0, 2).toUpperCase() ?? "AD"

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" }).catch(() => undefined)
    router.replace("/login")
    router.refresh()
  }

  const nav = <nav aria-label="Навигация администратора" className="space-y-1">
    {navigation.map(({ href, label, icon: Icon }) => <Link key={href} href={href} onClick={() => setMenuOpen(false)} className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${pathname === href ? "bg-ape-primary-soft text-ape-primary-text" : "text-muted-foreground hover:bg-accent hover:text-foreground"}`}><Icon className="size-4" />{label}</Link>)}
  </nav>

  return <div className="min-h-svh bg-muted/30 text-foreground">
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b bg-background/95 px-4 backdrop-blur md:px-6">
      <Link href="/admin" className="flex items-center gap-2 font-brand font-bold"><AcademicLogoIcon className="size-8" animate={false} /><span>Academic PE</span><span className="hidden rounded-md border border-ape-primary/30 bg-ape-primary-soft px-2 py-0.5 text-xs font-semibold text-ape-primary-text sm:inline">Администрирование</span></Link>
      <div className="flex items-center gap-2"><div className="hidden text-right sm:block"><p className="text-sm font-medium">Администратор</p><p className="text-xs text-muted-foreground">{session?.email}</p></div><Avatar className="size-8"><AvatarFallback>{initials}</AvatarFallback></Avatar><Button variant="ghost" size="icon" className="md:hidden" onClick={() => setMenuOpen(value => !value)} aria-label={menuOpen ? "Закрыть навигацию" : "Открыть навигацию"}>{menuOpen ? <X /> : <Menu />}</Button></div>
    </header>
    <div className="flex w-full"><aside className={`${menuOpen ? "block" : "hidden"} fixed inset-x-0 top-16 z-20 border-b bg-background p-4 shadow-lg md:static md:block md:min-h-[calc(100svh-4rem)] md:w-64 md:shrink-0 md:border-b-0 md:border-r md:p-4 md:shadow-none`}>{nav}<div className="mt-6 space-y-2 border-t pt-4"><Button variant="ghost" asChild className="w-full justify-start gap-3 text-muted-foreground"><Link href="/cabinet"><Gauge className="size-4" />К кабинету</Link></Button><Button variant="ghost" className="w-full justify-start gap-3 text-muted-foreground" onClick={logout}><LogOut className="size-4" />Выйти</Button></div></aside><main className="min-w-0 flex-1 p-4 sm:p-6 lg:p-8">{children}</main></div>
  </div>
}

export function AdminDashboard() {
  return <section className="space-y-6"><div><div className="flex items-center gap-2 text-sm text-ape-primary-text"><ShieldCheck className="size-4" />Защищённый раздел</div><h1 className="mt-1 text-3xl font-bold tracking-tight">Администрирование</h1><p className="mt-2 text-muted-foreground">Управляйте пользователями, глобальными ресурсами и состоянием платформы.</p></div><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><AdminSummary href="/admin/users" icon={UsersRound} title="Пользователи и роли" description="Управление доступом и ролями участников." /><AdminSummary href="/admin/resources" icon={Bot} title="Провайдеры и ресурсы" description="Глобальные credentials, модели и лимиты." /><AdminSummary href="/admin/jobs" icon={ClipboardList} title="Задания и очереди" description="Состояние обработчиков и фоновых заданий." /><AdminSummary href="/admin/audit" icon={Activity} title="Аудит и здоровье" description="Безопасные агрегаты и административные события." /></div></section>
}

function AdminSummary({ href, icon: Icon, title, description }: { href: string, icon: typeof UsersRound, title: string, description: string }) {
  return <Link href={href} className="rounded-xl border bg-card p-5 transition-colors hover:bg-accent"><Icon className="size-5 text-ape-primary" /><h2 className="mt-4 font-semibold">{title}</h2><p className="mt-1 text-sm text-muted-foreground">{description}</p></Link>
}
