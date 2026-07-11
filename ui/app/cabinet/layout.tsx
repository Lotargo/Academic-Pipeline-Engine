import { CabinetShell } from "@/app/components/cabinet-shell"

export default function CabinetLayout({ children }: { children: React.ReactNode }) {
  return <CabinetShell>{children}</CabinetShell>
}
