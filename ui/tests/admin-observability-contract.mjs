import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import test from "node:test"

const root = new URL("..", import.meta.url)

test("admin observability view proxies protected audit and health contracts", async () => {
  const [auditRoute, healthRoute, page, component, contract] = await Promise.all([
    readFile(new URL("app/api/admin/audit-events/route.ts", root), "utf8"),
    readFile(new URL("app/api/admin/health/route.ts", root), "utf8"),
    readFile(new URL("app/admin/audit/page.tsx", root), "utf8"),
    readFile(new URL("app/components/admin-observability.tsx", root), "utf8"),
    readFile(new URL("lib/admin-observability-contract.ts", root), "utf8"),
  ])

  assert.match(auditRoute, /`\/api\/auth\/admin\/audit-events\$\{query\}`/)
  assert.match(healthRoute, /"\/api\/auth\/admin\/health"/)
  assert.match(page, /<AdminObservability \/>/)
  assert.match(component, /\/api\/admin\/audit-events\?limit=50&offset=\$\{offset\}/)
  assert.match(component, /\/api\/admin\/health/)
  assert.match(component, /Показать следующие события/)
  assert.doesNotMatch(component, /metadata_json|event\.details|payload|api[_-]?key/i)
  assert.doesNotMatch(contract, /metadata_json|details|payload|credential/i)
  assert.match(contract, /correlation_id: z\.string\(\).*\.nullable\(\)/)
  assert.match(contract, /event_counts: z\.array/)
})
