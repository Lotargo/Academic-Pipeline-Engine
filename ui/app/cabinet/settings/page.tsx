import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export default function CabinetSettingsPage() {
  return <section className="max-w-2xl space-y-2"><h1 className="text-3xl font-bold tracking-tight">Настройки workspace</h1><p className="text-muted-foreground">Управление провайдерами и ресурсами будет добавлено в следующей композиции.</p><Card className="mt-6"><CardHeader><CardTitle>Пока нет доступных настроек</CardTitle><CardDescription>Этот экран сохраняет границу маршрута для будущих настроек и не выдаёт данные без подтверждённой сессии.</CardDescription></CardHeader></Card></section>
}
