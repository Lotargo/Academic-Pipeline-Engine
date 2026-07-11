import { NextResponse } from "next/server"

const backendUrl = () => process.env.BACKEND_API_URL || "http://127.0.0.1:8000"

export async function GET(request: Request) {
  const filename = new URL(request.url).searchParams.get("filename")
  if (!filename || filename.includes("..") || filename.includes("\\")) {
    return NextResponse.json({ detail: "Invalid download filename" }, { status: 400 })
  }
  const upstream = await fetch(`${backendUrl()}/api/download/${encodeURIComponent(filename)}`, { cache: "no-store" })
  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") || "application/octet-stream",
      "content-disposition": upstream.headers.get("content-disposition") || "attachment",
      "cache-control": "no-store",
    },
  })
}
