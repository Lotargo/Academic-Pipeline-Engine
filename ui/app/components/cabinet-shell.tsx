"use client"

import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { useState } from "react"
import { BookOpenText, CircleAlert, Database, FilePlus2, FolderKanban, History, ListChecks, LogOut, Menu, Settings2, X } from "lucide-react"
import { AcademicLogoIcon } from "@/app/components/academic-logo-icon"
import { useCabinetSession } from "@/app/components/session-gate"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

const navigation = [
  { href: "/cabinet", label: "Обзор", icon: FolderKanban },
  { href: "/cabinet/jobs", label: "Задания", icon: ListChecks },
  { href: "/cabinet/history", label: "История", icon: History },
  { href: "/", label: "Редактор", icon: FilePlus2 },
  { href: "/cabinet/settings", label: "Настройки", icon: Settings2 },
]

export function CabinetShell({ children }: { children: React.ReactNode }) {
  const session = useCabinetSession()
  const pathname = usePathname()
  const router = useRouter()
  const [menuOpen, setMenuOpen] = useState(false)

  if (!session) return <CabinetLoading />
  const workspace = session.workspaces[0]
  const initials = session.email.slice(0, 2).toUpperCase()

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" }).catch(() => undefined)
    router.replace("/login")
    router.refresh()
  }

  const nav = <nav aria-label="Основная навигация" className="space-y-1">
    {navigation.map(({ href, label, icon: Icon }) => <Link key={href} href={href} onClick={() => setMenuOpen(false)} className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${pathname === href ? "bg-ape-primary-soft text-ape-primary-text" : "text-muted-foreground hover:bg-accent hover:text-foreground"}`}><Icon className="size-4" />{label}</Link>)}
  </nav>

  return <div className="min-h-svh bg-muted/30 text-foreground">
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b bg-background/95 px-4 backdrop-blur md:px-6">
      <Link href="/cabinet" className="flex items-center gap-2 font-brand font-bold"><AcademicLogoIcon className="size-8" animate={false} /><span>Academic PE</span></Link>
      <div className="flex items-center gap-2"><div className="hidden text-right sm:block"><p className="text-sm font-medium">{workspace?.name ?? "Workspace"}</p><p className="text-xs text-muted-foreground">{session.email}</p></div><Avatar className="size-8"><AvatarFallback>{initials}</AvatarFallback></Avatar><Button variant="ghost" size="icon" className="md:hidden" onClick={() => setMenuOpen(value => !value)} aria-label={menuOpen ? "Закрыть навигацию" : "Открыть навигацию"}>{menuOpen ? <X /> : <Menu />}</Button></div>
    </header>
    <div className="flex w-full">
      <aside className={`${menuOpen ? "block" : "hidden"} fixed inset-x-0 top-16 z-20 border-b bg-background p-4 shadow-lg md:static md:block md:min-h-[calc(100svh-4rem)] md:w-60 md:shrink-0 md:border-b-0 md:border-r md:p-4 md:shadow-none`}>{nav}<div className="mt-6 border-t pt-4"><Button variant="ghost" className="w-full justify-start gap-3 text-muted-foreground" onClick={logout}><LogOut className="size-4" />Выйти</Button></div></aside>
      <main className="min-w-0 flex-1 p-4 sm:p-6 lg:p-8">{children}</main>
    </div>
  </div>
}

export function CabinetDashboard() {
  const session = useCabinetSession()
  if (!session) return <CabinetLoading />
  const workspace = session.workspaces[0]
  if (!workspace) return <section className="mx-auto max-w-xl py-20"><Card><CardHeader><CircleAlert className="size-6 text-destructive" /><CardTitle>Рабочее пространство недоступно</CardTitle><CardDescription>У вашей учётной записи нет активного workspace. Обратитесь к администратору.</CardDescription></CardHeader></Card></section>
  return <section className="space-y-7"><div><p className="text-sm text-muted-foreground">Рабочее пространство</p><div className="mt-1 flex flex-wrap items-center gap-2"><h1 className="text-3xl font-bold tracking-tight">{workspace.name}</h1><span className="rounded-full bg-ape-primary-soft px-2.5 py-1 text-xs font-semibold text-ape-primary-text">{workspace.role === "owner" ? "Владелец" : "Участник"}</span></div><p className="mt-2 text-sm text-muted-foreground">ID: <span className="font-mono">{workspace.id}</span></p></div>
    <div className="grid gap-4 sm:grid-cols-2"><SummaryCard icon={BookOpenText} title="Провайдеры" value="Не настроены" description="Подключение AI- и OCR-провайдеров появится в настройках провайдеров." href="/cabinet/settings" action="Открыть настройки" /><SummaryCard icon={Database} title="Ресурсы" value="Нет данных" description="Сводка глобальных и ваших ресурсов будет доступна после подключения API." /></div>
    <Card><CardHeader><CardTitle>Начните работу</CardTitle><CardDescription>Создайте новую задачу в редакторе. История, артефакты и живой статус появятся в следующих разделах кабинета.</CardDescription></CardHeader><CardContent><Button asChild><Link href="/"><FilePlus2 />Открыть редактор</Link></Button></CardContent></Card>
  </section>
}

function SummaryCard({ icon: Icon, title, value, description, href, action }: { icon: typeof Database, title: string, value: string, description: string, href?: string, action?: string }) {
  return <Card><CardHeader><div className="flex items-center justify-between"><Icon className="size-5 text-ape-primary" /><span className="text-sm font-semibold">{value}</span></div><CardTitle className="text-lg">{title}</CardTitle><CardDescription>{description}</CardDescription></CardHeader>{href && <CardContent><Button asChild variant="outline" size="sm"><Link href={href}>{action}</Link></Button></CardContent>}</Card>
}

function CabinetLoading() {
  return <main className="w-full p-6" aria-live="polite"><p className="sr-only">Загружаем кабинет</p><Skeleton className="h-12 w-full" /><div className="mt-8 grid gap-4 sm:grid-cols-2"><Skeleton className="h-44" /><Skeleton className="h-44" /></div></main>
}
