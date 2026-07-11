import { providerResponse } from "@/lib/provider-server"

export async function POST(request: Request) {
  return providerResponse("/api/credentials", { method: "POST", headers: { "content-type": "application/json" }, body: await request.text() }, request.headers.get("cookie"))
}
