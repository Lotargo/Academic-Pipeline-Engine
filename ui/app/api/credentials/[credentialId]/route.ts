import { providerResponse } from "@/lib/provider-server"

export async function PATCH(request: Request, { params }: { params: Promise<{ credentialId: string }> }) {
  return providerResponse(`/api/credentials/${encodeURIComponent((await params).credentialId)}`, { method: "PATCH", headers: { "content-type": "application/json" }, body: await request.text() }, request.headers.get("cookie"))
}

export async function DELETE(request: Request, { params }: { params: Promise<{ credentialId: string }> }) {
  return providerResponse(`/api/credentials/${encodeURIComponent((await params).credentialId)}`, { method: "DELETE" }, request.headers.get("cookie"))
}
