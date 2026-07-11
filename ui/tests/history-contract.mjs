import assert from "node:assert/strict"
import test from "node:test"
import { readFile } from "node:fs/promises"

test("history UI uses cursor pagination and does not expose storage keys", async () => {
  const [contract, component] = await Promise.all([
    readFile(new URL("../../dev_docs_part_2/contracts/history-artifact-api.md", import.meta.url), "utf8"),
    readFile(new URL("../app/components/history-workspace.tsx", import.meta.url), "utf8"),
  ])
  assert.match(contract, /next_cursor/)
  assert.match(contract, /Storage keys.*never included/)
  assert.match(component, /params\.set\("cursor", next\)/)
  assert.match(component, /artifacts\/\$\{encodeURIComponent\(artifact\.id\)\}\/download/)
  assert.match(component, /err\.status === 410/)
  assert.match(component, /Array\.isArray\(value\)/)
  assert.match(component, /artifact\.id\.startsWith\("legacy:"\)/)
  assert.match(component, /api\/legacy-download\?filename=/)
})
