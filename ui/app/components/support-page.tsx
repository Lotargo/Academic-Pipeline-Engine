"use client"

import { useMemo, useState } from "react"
import { HeartHandshake, MessageCircleMore, QrCode, ShieldCheck } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

const suggestedAmounts = [150, 500, 1000, 5000]

export type SupportConfig = {
  sbpUrlTemplate: string
  sbpQrUrlTemplate: string
  telegramUrl: string
}

function externalUrl(value: string) {
  try {
    const url = new URL(value)
    return url.protocol === "https:" ? url.toString() : null
  } catch { return null }
}

function configuredUrl(template: string, amount: number) {
  return externalUrl(template.replaceAll("{amount}", String(amount)))
}

export function SupportPage({ config }: { config: SupportConfig }) {
  const [amount, setAmount] = useState(500)
  const [customAmount, setCustomAmount] = useState("")
  const selectedAmount = Number.isSafeInteger(amount) && amount > 0 ? amount : 500
  const paymentUrl = useMemo(() => configuredUrl(config.sbpUrlTemplate, selectedAmount), [config.sbpUrlTemplate, selectedAmount])
  const qrUrl = useMemo(() => configuredUrl(config.sbpQrUrlTemplate, selectedAmount), [config.sbpQrUrlTemplate, selectedAmount])
  const telegramUrl = useMemo(() => externalUrl(config.telegramUrl), [config.telegramUrl])

  function chooseCustom(value: string) {
    setCustomAmount(value)
    const next = Number(value)
    if (Number.isSafeInteger(next) && next > 0 && next <= 1_000_000) setAmount(next)
  }

  return <main className="mx-auto w-full max-w-5xl px-4 py-10 sm:px-6 lg:py-16">
    <div className="max-w-3xl"><p className="text-sm font-medium text-ape-primary-text">Academic Pipeline Engine</p><h1 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">Поддержка и сотрудничество</h1><p className="mt-4 text-muted-foreground">Academic PE доступен без платных тарифов. Если проект оказался полезен, вы можете добровольно поддержать его. Перевод не даёт преимуществ в функциях, лимитах или очереди.</p></div>
    <div className="mt-8 grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><HeartHandshake className="size-5 text-ape-primary" />Добровольная поддержка</CardTitle><CardDescription>Выберите удобную сумму или укажите свою. Это не покупка услуги и не подписка.</CardDescription></CardHeader>
        <CardContent className="space-y-5">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">{suggestedAmounts.map(value => <Button key={value} type="button" variant={value === selectedAmount && !customAmount ? "default" : "outline"} onClick={() => { setCustomAmount(""); setAmount(value) }}>{value.toLocaleString("ru-RU")} ₽</Button>)}</div>
          <div className="space-y-2"><Label htmlFor="support-custom-amount">Другая сумма, ₽</Label><Input id="support-custom-amount" type="number" min="1" max="1000000" inputMode="numeric" value={customAmount} onChange={event => chooseCustom(event.target.value)} placeholder="Например, 750" /><p className="text-xs text-muted-foreground">Сумма подставляется в публичный шаблон СБП только после его настройки оператором.</p></div>
          {paymentUrl ? <Button asChild className="w-full sm:w-auto"><a href={paymentUrl} target="_blank" rel="noopener noreferrer">Открыть перевод СБП на {selectedAmount.toLocaleString("ru-RU")} ₽</a></Button> : <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">Ссылка для перевода ещё не опубликована. Пожалуйста, вернитесь позже.</p>}
          <p className="flex gap-2 text-xs text-muted-foreground"><ShieldCheck className="mt-0.5 size-4 shrink-0" />Мы не связываем поддержку с аккаунтом и не обещаем встречных услуг, приоритета или расширения доступа.</p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><QrCode className="size-5 text-ape-primary" />QR-код СБП</CardTitle><CardDescription>Отсканируйте код банковским приложением и проверьте получателя перед подтверждением перевода.</CardDescription></CardHeader>
        <CardContent>{qrUrl ? <div className="space-y-4"><div className="mx-auto w-fit rounded-xl border bg-white p-3"><img src={qrUrl} width="256" height="256" alt={`QR-код СБП для добровольной поддержки на ${selectedAmount.toLocaleString("ru-RU")} ₽`} /></div><p className="text-center text-sm text-muted-foreground">Выбрано: {selectedAmount.toLocaleString("ru-RU")} ₽</p></div> : <p className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">QR-код будет опубликован вместе с проверенными реквизитами СБП.</p>}</CardContent>
      </Card>
    </div>
    <Card className="mt-6"><CardHeader><CardTitle className="flex items-center gap-2"><MessageCircleMore className="size-5 text-ape-primary" />Сотрудничество</CardTitle><CardDescription>Для коммерческих предложений, партнёрств и иных рабочих вопросов используйте отдельный публичный Telegram-канал.</CardDescription></CardHeader><CardContent>{telegramUrl ? <Button asChild variant="outline"><a href={telegramUrl} target="_blank" rel="noopener noreferrer">Написать в Telegram</a></Button> : <p className="text-sm text-muted-foreground">Публичный Telegram для сотрудничества готовится к публикации.</p>}<p className="mt-4 text-xs text-muted-foreground">Обсуждение сотрудничества не является продажей доступа к Academic PE.</p></CardContent></Card>
  </main>
}
