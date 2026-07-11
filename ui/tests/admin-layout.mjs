import assert from "node:assert/strict"
import test from "node:test"

const base = process.env.TEST_BASE_URL || "http://127.0.0.1:3100"

test("admin route waits for a confirmed session before rendering admin navigation", async () => {
  const response = await fetch(`${base}/admin`)
  const html = await response.text()
  assert.equal(response.status, 200)
  assert.match(html, /Восстанавливаем сессию/)
  assert.doesNotMatch(html, /Пользователи и роли/)
})

test("admin shell is isolated from the cabinet navigation", async () => {
  const source = await (await fetch(`${base}/admin`)).text()
  assert.doesNotMatch(source, /Основная навигация/)
})
