import type React from "react"
import type { Metadata } from "next"
import { IBM_Plex_Mono, IBM_Plex_Sans, Space_Grotesk } from "next/font/google"
import { Analytics } from "@vercel/analytics/next"
import { Toaster } from "@/components/ui/sonner"
import { ThemeProvider } from "@/components/theme-provider"
import "./globals.css"
import { SessionGate } from "@/app/components/session-gate"

const uiFont = IBM_Plex_Sans({
  subsets: ["latin", "cyrillic"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-ape-ui",
})

const monoFont = IBM_Plex_Mono({
  subsets: ["latin", "cyrillic"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-ape-mono",
})

const brandFont = Space_Grotesk({
  subsets: ["latin"],
  weight: ["600", "700"],
  variable: "--font-ape-brand",
})

export const metadata: Metadata = {
  title: "Academic PE - AI Documentation Engine",
  description: "Academic Pipeline Engine - Enterprise-grade AI academic and technical paper generation platform",
  icons: {
    icon: "/icon.svg",
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${uiFont.variable} ${monoFont.variable} ${brandFont.variable} font-sans antialiased`}>
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
          <SessionGate>{children}</SessionGate>
          <Toaster />
          <Analytics />
        </ThemeProvider>
      </body>
    </html>
  )
}
