import { SupportPage } from "@/app/components/support-page"

export default function Support() {
  return <SupportPage config={{
    yoomoneyReceiver: process.env.NEXT_PUBLIC_SUPPORT_YOOMONEY_RECEIVER || "",
    telegramUrl: process.env.NEXT_PUBLIC_SUPPORT_TELEGRAM_URL || "",
  }} />
}
