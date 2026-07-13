import assert from "node:assert/strict"
import test from "node:test"

const base = process.env.TEST_BASE_URL || "http://127.0.0.1:3100"

test("service login presents provider icons and the service-dev email mock", async () => {
  const response = await fetch(`${base}/login`)
  const html = await response.text()
  assert.equal(response.status, 200)
  assert.match(html, /Продолжить с Google/)
  assert.match(html, /Продолжить с Яндексом/)
  assert.match(html, /Режим service-dev/)
  assert.match(html, /id="email"/)
  assert.match(html, /Продолжить с email/)
  assert.match(html, /Подтверждение email появится после настройки почтового сервиса/)
  assert.doesNotMatch(html, /id="password"/)
})

test("callback states stay reachable before real OAuth deployment", async () => {
  const response = await fetch(`${base}/auth/callback?status=denied`)
  const html = await response.text()
  assert.equal(response.status, 200)
  assert.match(html, /Доступ не предоставлен/)
  assert.match(html, /Вернуться к выбору провайдера/)
})

test("mock provider start and callback keep the identity token in an HttpOnly cookie", async () => {
  const start = await fetch(`${base}/api/auth/providers/google/start`, { redirect: "manual" })
  assert.equal(start.status, 307)
  const startLocation = new URL(start.headers.get("location") || "", base)
  assert.equal(startLocation.origin, new URL(base).origin)
  assert.match(startLocation.toString(), /\/api\/auth\/callback\?provider=google&mock_provider=google/)
  const callback = await fetch(new URL(start.headers.get("location"), base), { redirect: "manual" })
  assert.equal(callback.status, 307)
  const cookies = callback.headers.get("set-cookie") || ""
  assert.match(cookies, /ape_identity_access=mock%3Agoogle/)
  assert.match(cookies, /HttpOnly/)
  const callbackLocation = new URL(callback.headers.get("location") || "", base)
  assert.equal(callbackLocation.origin, new URL(base).origin)
  assert.match(callbackLocation.toString(), /\/auth\/callback\?status=complete/)
})

test("service-dev email mock sets an HttpOnly identity cookie without sending a code", async () => {
  const response = await fetch(`${base}/api/auth/email/start`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email: "researcher@example.org" }),
  })
  assert.equal(response.status, 200)
  assert.deepEqual(await response.json(), { ok: true })
  const cookies = response.headers.get("set-cookie") || ""
  assert.match(cookies, /ape_identity_access=mock%3Aemail%3Aresearcher%40example\.org/)
  assert.match(cookies, /HttpOnly/)
})

test("service-dev email mock rejects malformed and reserved email domains", async () => {
  const response = await fetch(`${base}/api/auth/email/start`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email: "researcher@example.test" }),
  })
  assert.equal(response.status, 400)
  assert.deepEqual(await response.json(), { detail: "Введите корректный email" })
})

test("service provider session is forwarded to protected API routes", async () => {
  const response = await fetch(`${base}/api/jobs`, {
    headers: { cookie: "ape_identity_access=mock%3Agoogle" },
  })
  assert.notEqual(response.status, 401)
})

test("session restore rejects a missing protected cookie", async () => {
  const response = await fetch(`${base}/api/auth/session`)
  assert.equal(response.status, 401)
  assert.deepEqual(await response.json(), { authenticated: false, reason: "missing" })
})

test("cabinet waits for session confirmation before exposing workspace data", async () => {
  const response = await fetch(`${base}/cabinet`)
  const html = await response.text()
  assert.equal(response.status, 200)
  assert.match(html, /Восстанавливаем сессию/)
  assert.doesNotMatch(html, /Провайдеры/)
})
