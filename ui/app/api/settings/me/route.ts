import { providerResponse } from "@/lib/provider-server"

export async function GET(request: Request) {
  return providerResponse("/api/settings/me", undefined, request.headers.get("cookie"))
}

export async function PUT(request: Request) {
  return providerResponse(
    "/api/settings/me",
    { method: "PUT", headers: { "content-type": "application/json" }, body: await request.text() },
    request.headers.get("cookie"),
  )
}
