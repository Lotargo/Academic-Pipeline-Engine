import { cookies } from "next/headers"
import { NextResponse } from "next/server"
import { ACCESS_COOKIE } from "@/lib/auth-server"

const backendUrl = () => process.env.BACKEND_API_URL || "http://127.0.0.1:8000"

function cookieToken(cookieHeader?: string | null) {
  const encoded = cookieHeader?.split(";").map(part => part.trim()).find(part => part.startsWith(`${ACCESS_COOKIE}=`))?.slice(ACCESS_COOKIE.length + 1)
  return encoded ? decodeURIComponent(encoded) : undefined
}

export async function jobsBackend(path: string, init: RequestInit = {}, cookieHeader?: string | null) {
  const token = cookieToken(cookieHeader) || (await cookies()).get(ACCESS_COOKIE)?.value
  if (!token) return null
  const headers = new Headers(init.headers)
  headers.set("authorization", `Bearer ${token}`)
  return fetch(`${backendUrl()}${path}`, { ...init, headers, cache: "no-store" })
}

export async function jobsResponse(path: string, init?: RequestInit, cookieHeader?: string | null) {
  const upstream = await jobsBackend(path, init, cookieHeader)
  if (!upstream) return NextResponse.json({ detail: "Authentication required" }, { status: 401 })
  const body = await upstream.text()
  return new NextResponse(body, { status: upstream.status, headers: { "content-type": upstream.headers.get("content-type") || "application/json", "cache-control": "no-store" } })
}
