import { cookies } from "next/headers"
import { NextResponse } from "next/server"
import { ACCESS_COOKIE } from "@/lib/auth-server"
import { IDENTITY_ACCESS_COOKIE } from "@/lib/provider-auth-server"

const backendUrl = () => process.env.BACKEND_API_URL || "http://127.0.0.1:8000"
const ACCESS_COOKIES = [IDENTITY_ACCESS_COOKIE, ACCESS_COOKIE]

function cookieToken(cookieHeader?: string | null) {
  for (const name of ACCESS_COOKIES) {
    const encoded = cookieHeader?.split(";").map(part => part.trim()).find(part => part.startsWith(`${name}=`))?.slice(name.length + 1)
    if (encoded) return decodeURIComponent(encoded)
  }
  return undefined
}

export async function providerBackend(path: string, init: RequestInit = {}, cookieHeader?: string | null) {
  const jar = await cookies()
  const token = cookieToken(cookieHeader) || jar.get(IDENTITY_ACCESS_COOKIE)?.value || jar.get(ACCESS_COOKIE)?.value
  if (!token) return null
  const headers = new Headers(init.headers)
  headers.set("authorization", `Bearer ${token}`)
  return fetch(`${backendUrl()}${path}`, { ...init, headers, cache: "no-store" })
}

export async function providerResponse(path: string, init?: RequestInit, cookieHeader?: string | null) {
  const upstream = await providerBackend(path, init, cookieHeader)
  if (!upstream) return NextResponse.json({ detail: "Authentication required" }, { status: 401 })
  const body = await upstream.text()
  return new NextResponse(body, { status: upstream.status, headers: { "content-type": upstream.headers.get("content-type") || "application/json", "cache-control": "no-store" } })
}
