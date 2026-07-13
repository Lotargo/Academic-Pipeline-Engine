import assert from "node:assert/strict"
import test from "node:test"
import { readFile } from "node:fs/promises"

test("provider settings keep credentials masked and require explicit destructive actions", async () => {
  const [contract, component, parser, proxy, settingsRoute, rewrite, personal] = await Promise.all([
    readFile(new URL("../../dev_docs_part_2/contracts/provider-settings-api.md", import.meta.url), "utf8"),
    readFile(new URL("../app/components/provider-settings.tsx", import.meta.url), "utf8"),
    readFile(new URL("../lib/provider-contract.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/api/credentials/[credentialId]/route.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/api/settings/me/route.ts", import.meta.url), "utf8"),
    readFile(new URL("../next.config.mjs", import.meta.url), "utf8"),
    readFile(new URL("../app/components/personal-settings.tsx", import.meta.url), "utf8"),
  ])
  assert.match(contract, /никогда не содержит.*secret/i)
  assert.match(contract, /Точный остаток.*квота/i)
  assert.match(component, /type="password"/)
  assert.match(component, /autoComplete="new-password"/)
  assert.match(component, /AlertDialog/)
  assert.match(component, /credential_policy/)
  assert.match(component, /best-effort/i)
  assert.doesNotMatch(component, /window\.localStorage/)
  assert.match(parser, /masked_value: "••••••••"/)
  assert.doesNotMatch(parser, /\.secret/)
  assert.match(proxy, /method: "PATCH"/)
  assert.match(proxy, /method: "DELETE"/)
  assert.match(settingsRoute, /providerResponse\("\/api\/settings\/me"/)
  assert.match(rewrite, /provider-settings\|credentials\|settings/)
  assert.match(personal, /\/api\/settings\/me/)
  assert.doesNotMatch(personal, /localStorage/)
})
