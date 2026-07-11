import assert from "node:assert/strict"
import test from "node:test"

const base = process.env.TEST_BASE_URL || "http://127.0.0.1:3100"

test("login page exposes an accessible credential form", async () => {
  const response = await fetch(`${base}/login`)
  const html = await response.text()
  assert.equal(response.status, 200)
  assert.match(html, /С возвращением/)
  assert.match(html, /id="email"/)
  assert.match(html, /id="password"/)
  assert.match(html, /href="\/register"/)
})

test("registration page has no role selection", async () => {
  const response = await fetch(`${base}/register`)
  const html = await response.text()
  assert.equal(response.status, 200)
  assert.match(html, /Создать аккаунт/)
  assert.doesNotMatch(html, /name="role"/)
  assert.doesNotMatch(html, /Администратор/)
})

test("session restore rejects a missing protected cookie", async () => {
  const response = await fetch(`${base}/api/auth/session`)
  assert.equal(response.status, 401)
  assert.deepEqual(await response.json(), { authenticated: false, reason: "missing" })
})
