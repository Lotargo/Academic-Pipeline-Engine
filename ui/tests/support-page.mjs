import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import test from "node:test"

const root = new URL("..", import.meta.url)

test("support page offers voluntary amounts without paid entitlements", async () => {
  const source = await readFile(new URL("app/components/support-page.tsx", root), "utf8")
  for (const amount of [150, 500, 1000, 5000]) assert.match(source, new RegExp(String(amount)))
  assert.match(source, /не даёт преимуществ в функциях, лимитах или очереди/)
  assert.match(source, /не покупка услуги и не подписка/)
  assert.doesNotMatch(source, /premium|priority support|paid plan/i)
})

test("support page protects external payment and contact links", async () => {
  const source = await readFile(new URL("app/components/support-page.tsx", root), "utf8")
  assert.match(source, /url\.protocol === "https:"/)
  assert.match(source, /target="_blank" rel="noopener noreferrer"/)
  assert.match(source, /QR-код СБП/)
  assert.match(source, /Telegram/)
})

test("support is a public route and credentials are not configured in source", async () => {
  const [gate, page, config] = await Promise.all([
    readFile(new URL("app/components/session-gate.tsx", root), "utf8"),
    readFile(new URL("app/support/page.tsx", root), "utf8"),
    readFile(new URL(".env.example", root), "utf8"),
  ])
  assert.match(gate, /pathname === "\/support"/)
  assert.match(page, /NEXT_PUBLIC_SUPPORT_SBP_URL_TEMPLATE/)
  assert.match(config, /Never put API keys here/)
})
