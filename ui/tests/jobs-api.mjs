import assert from "node:assert/strict"
import test from "node:test"

const base = process.env.TEST_BASE_URL || "http://127.0.0.1:3100"

function cookies(response) {
  const values = typeof response.headers.getSetCookie === "function" ? response.headers.getSetCookie() : [response.headers.get("set-cookie") || ""]
  return values.map(value => value.split(";")[0]).filter(Boolean).join("; ")
}

test("jobs proxy preserves the authenticated session for create and cancellation", async () => {
  const email = `jobs-e2e-${crypto.randomUUID()}@example.com`
  const registered = await fetch(`${base}/api/auth/register`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ email, password: "correct horse battery staple" }) })
  assert.equal(registered.status, 201)
  const cookie = cookies(registered)
  assert.match(cookie, /ape_access=/)

  const created = await fetch(`${base}/api/jobs`, { method: "POST", headers: { "content-type": "application/json", cookie }, body: JSON.stringify({ kind: "pipeline", topic: "E2E job" }) })
  assert.equal(created.status, 201)
  const job = await created.json()
  assert.equal(job.status, "pending")

  const cancelled = await fetch(`${base}/api/jobs/${job.id}/cancel`, { method: "POST", headers: { cookie } })
  assert.equal(cancelled.status, 202)
  assert.ok((await cancelled.json()).cancel_requested_at)
})
