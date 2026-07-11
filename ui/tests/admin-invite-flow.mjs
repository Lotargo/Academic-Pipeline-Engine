import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import test from "node:test"

const root = new URL("..", import.meta.url)

test("admin invite activation keeps the token ephemeral and requires confirmation", async () => {
  const source = await readFile(new URL("app/components/admin-invite-activation.tsx", root), "utf8")
  assert.match(source, /type="password"/)
  assert.match(source, /Активировать роль администратора\?/) 
  assert.match(source, /router\.replace\("\/login\?reason=admin_activated"\)/)
  assert.doesNotMatch(source, /localStorage|sessionStorage/)
})

test("activation proxy clears browser auth cookies only after backend success", async () => {
  const source = await readFile(new URL("app/api/admin-invites/activate/route.ts", root), "utf8")
  assert.match(source, /providerBackend\(/)
  assert.match(source, /clearSession\(new NextResponse\(null, \{ status: 204 \}\)\)/)
  assert.match(source, /"\/api\/auth\/admin-invites\/activate"/)
})
