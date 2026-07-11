"use client"
import { createContext, useContext, useEffect, useState } from "react"
import { usePathname, useRouter } from "next/navigation"
import { Loader2 } from "lucide-react"
import type { SessionContext, SessionPayload } from "@/lib/auth-contract"

const CabinetSessionContext = createContext<SessionContext | null>(null)

export const useCabinetSession = () => useContext(CabinetSessionContext)

export function SessionGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname(); const router = useRouter(); const isPublic = pathname === "/login" || pathname === "/register" || pathname === "/support"; const [ready, setReady] = useState(isPublic); const [session, setSession] = useState<SessionContext | null>(null)
  useEffect(() => {
    if (isPublic) { setReady(true); return }
    setReady(false)
    let active = true
    fetch("/api/auth/session", { cache: "no-store" }).then(async response => {
      if (!active) return
      if (response.ok) { const payload = await response.json() as SessionPayload; setSession(payload.context); setReady(true) }
      else { const body = await response.json().catch(() => ({})); router.replace(`/login?reason=${body.reason || "expired"}`) }
    }).catch(() => router.replace("/login?reason=unavailable"))
    return () => { active = false }
  }, [isPublic, router])
  if (!ready) return <main className="grid min-h-svh place-items-center" aria-live="polite"><div className="flex items-center gap-3 text-muted-foreground"><Loader2 className="size-5 animate-spin"/>Восстанавливаем сессию…</div></main>
  return <CabinetSessionContext.Provider value={session}>{children}</CabinetSessionContext.Provider>
}

export function AdminGate({ children }: { children: React.ReactNode }) {
  const session = useCabinetSession()
  const router = useRouter()

  useEffect(() => {
    if (session && session.role !== "admin") router.replace("/cabinet")
  }, [router, session])

  if (!session || session.role !== "admin") {
    return <main className="grid min-h-svh place-items-center" aria-live="polite"><div className="flex items-center gap-3 text-muted-foreground"><Loader2 className="size-5 animate-spin"/>Проверяем права администратора…</div></main>
  }

  return <>{children}</>
}
