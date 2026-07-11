import type { ReactNode } from "react"
import { AcademicLogoIcon } from "./academic-logo-icon"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export function AuthShell({ title, description, children }: { title: string, description: string, children: ReactNode }) {
  return <main className="relative grid min-h-svh place-items-center overflow-hidden bg-background px-4 py-10"><div aria-hidden="true" className="absolute inset-0 bg-[radial-gradient(circle_at_20%_10%,color-mix(in_oklab,var(--ape-primary)_16%,transparent),transparent_38%),radial-gradient(circle_at_80%_90%,color-mix(in_oklab,var(--ape-primary)_10%,transparent),transparent_34%)]"/><div className="relative w-full max-w-md"><div className="mb-6 flex items-center justify-center gap-3"><AcademicLogoIcon className="size-12" animate={false}/><div><div className="font-brand text-lg font-bold">Academic PE</div><div className="text-xs uppercase tracking-[.16em] text-muted-foreground">Pipeline Engine</div></div></div><Card className="shadow-xl shadow-black/5"><CardHeader><CardTitle className="text-2xl">{title}</CardTitle><CardDescription>{description}</CardDescription></CardHeader><CardContent>{children}</CardContent></Card><p className="mt-5 text-center text-xs text-muted-foreground">Безопасная сессия хранится в защищённой cookie этого браузера.</p></div></main>
}
