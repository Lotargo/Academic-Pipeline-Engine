import { SupportPage } from "@/app/components/support-page"

export default function Support() {
  return <SupportPage config={{
    sbpUrlTemplate: process.env.NEXT_PUBLIC_SUPPORT_SBP_URL_TEMPLATE || "",
    sbpQrUrlTemplate: process.env.NEXT_PUBLIC_SUPPORT_SBP_QR_URL_TEMPLATE || "",
    telegramUrl: process.env.NEXT_PUBLIC_SUPPORT_TELEGRAM_URL || "",
  }} />
}
