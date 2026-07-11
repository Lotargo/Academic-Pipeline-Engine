"use client"
import { useEffect, useState } from "react"
import { usePathname, useRouter } from "next/navigation"
import { Loader2 } from "lucide-react"

export function SessionGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname(); const router = useRouter(); const [ready, setReady] = useState(pathname === "/login" || pathname === "/register")
  useEffect(() => {
    if (pathname === "/login" || pathname === "/register") return
    let active = true
    fetch("/api/auth/session", { cache: "no-store" }).then(async response => {
      if (!active) return
      if (response.ok) setReady(true)
      else { const body = await response.json().catch(() => ({})); router.replace(`/login?reason=${body.reason || "expired"}`) }
    }).catch(() => router.replace("/login?reason=unavailable"))
    return () => { active = false }
  }, [pathname, router])
  if (!ready) return <main className="grid min-h-svh place-items-center" aria-live="polite"><div className="flex items-center gap-3 text-muted-foreground"><Loader2 className="size-5 animate-spin"/>Восстанавливаем сессию…</div></main>
  return children
}
