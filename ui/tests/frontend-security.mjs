import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import test from "node:test"

const root = new URL("..", import.meta.url)

test("security headers use a restrictive CSP without wildcard sources", async () => {
  const source = await readFile(new URL("next.config.mjs", root), "utf8")
  for (const directive of ["default-src 'self'", "object-src 'none'", "frame-ancestors 'none'", "form-action 'self'", "connect-src 'self'"]) assert.match(source, new RegExp(directive.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")))
  assert.match(source, /X-Content-Type-Options/)
  assert.match(source, /Strict-Transport-Security/)
  assert.doesNotMatch(source, /https:\/\/\*/)
})

test("unsafe API methods reject declared cross-origin requests", async () => {
  const source = await readFile(new URL("proxy.ts", root), "utf8")
  assert.match(source, /const unsafeMethods = new Set\(\["DELETE", "PATCH", "POST", "PUT"\]\)/)
  assert.match(source, /Cross-origin request denied/)
  assert.match(source, /matcher: "\/api\/:path\*"/)
})

test("session secrets are cookie-only and CSS interpolation is constrained", async () => {
  const [auth, providerAuth, inventory, chart] = await Promise.all([
    readFile(new URL("lib/auth-server.ts", root), "utf8"),
    readFile(new URL("lib/provider-auth-server.ts", root), "utf8"),
    readFile(new URL("../dev_docs_part_2/frontend/FE-08-frontend-security/SECURITY_INVENTORY.md", root), "utf8"),
    readFile(new URL("components/ui/chart.tsx", root), "utf8"),
  ])
  assert.match(auth, /httpOnly: true/)
  assert.match(auth, /sameSite: "lax"/)
  assert.match(providerAuth, /httpOnly: true/)
  assert.match(providerAuth, /PKCE_VERIFIER_COOKIE/)
  assert.doesNotMatch(providerAuth, /localStorage/)
  assert.match(inventory, /no raw HTML parser/)
  assert.match(chart, /function isSafeCssColor/)
  assert.match(chart, /\^\[a-z0-9-\]\+\$/)
})
