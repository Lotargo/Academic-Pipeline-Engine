import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import test from "node:test"

const root = new URL("..", import.meta.url)

test("service editor creates workspace jobs and never reads global legacy status", async () => {
  const [page, editor, adapter] = await Promise.all([
    readFile(new URL("app/page.tsx", root), "utf8"),
    readFile(new URL("app/components/service-editor.tsx", root), "utf8"),
    readFile(new URL("lib/editor-adapter.ts", root), "utf8"),
  ])
  assert.match(page, /editorRuntimeProfile\(\) === "service"/)
  assert.match(editor, /\/api\/jobs\//)
  assert.doesNotMatch(editor, /\/api\/(?:run|status|cancel)/)
  assert.match(adapter, /createEditorJob/)
  assert.match(adapter, /fetch\("\/api\/run"/)
})

test("editor, jobs, and history share job deep links", async () => {
  const [editor, jobs, history] = await Promise.all([
    readFile(new URL("app/components/service-editor.tsx", root), "utf8"),
    readFile(new URL("app/components/jobs-workspace.tsx", root), "utf8"),
    readFile(new URL("app/components/history-workspace.tsx", root), "utf8"),
  ])
  for (const source of [editor, jobs, history]) assert.match(source, /\?job=\$\{encodeURIComponent\(.*id\)\}/)
  assert.match(jobs, /useSearchParams/)
})

test("editor job contract preserves advanced options", async () => {
  const [contract, client] = await Promise.all([
    readFile(new URL("lib/job-contract.ts", root), "utf8"),
    readFile(new URL("lib/job-client.ts", root), "utf8"),
  ])
  for (const field of ["academic_mode", "author", "continuation_source", "artifact_override", "web_search_enabled", "attachments"]) assert.match(contract, new RegExp(field))
  assert.match(client, /editor_options: editorOptions/)
})

test("local-first and service launch configuration select their editor profiles explicitly", async () => {
  const [local, serviceCompose, localWindows] = await Promise.all([
    readFile(new URL("../run-local.sh", root), "utf8"),
    readFile(new URL("../docker-compose.service-dev.yml", root), "utf8"),
    readFile(new URL("../run-local.bat", root), "utf8"),
  ])
  for (const source of [local, localWindows]) assert.match(source, /NEXT_PUBLIC_APE_RUNTIME_PROFILE=local/)
  assert.match(serviceCompose, /NEXT_PUBLIC_APE_RUNTIME_PROFILE: service/)
})
