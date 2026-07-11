import { AdminShell } from "@/app/components/admin-shell"
import { AdminGate } from "@/app/components/session-gate"

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return <AdminGate><AdminShell>{children}</AdminShell></AdminGate>
}
