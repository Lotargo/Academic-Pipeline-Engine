import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import test from "node:test"

const root = new URL("..", import.meta.url)

test("READY document UI keeps revision optional and submits the latest ready version", async () => {
  const preview = await readFile(new URL("app/components/document-preview.tsx", root), "utf8")

  assert.match(preview, /const feedback = revisionFeedback\.trim\(\)/)
  assert.match(preview, /if \(!feedback \|\| !runId\) return/)
  assert.match(preview, /disabled=\{submittingRevision \|\| !revisionFeedback\.trim\(\)\}/)
  assert.match(preview, /\/api\/runs\/\$\{encodeURIComponent\(runId\)\}\/revisions/)
  assert.match(preview, /base_revision: baseRevision, feedback/)
  assert.match(preview, /readyRevisions\[readyRevisions\.length - 1\]/)
  assert.match(preview, /Текущая версия: \{baseRevision\}/)
  assert.match(preview, /\{runId && \(/)
})

test("revision API remains versioned, patch-first, and exports the latest ready context", async () => {
  const [server, revision] = await Promise.all([
    readFile(new URL("../academic_pe/server.py", root), "utf8"),
    readFile(new URL("../academic_pe/core/revision.py", root), "utf8"),
  ])

  assert.match(server, /@app\.post\("\/api\/runs\/\{run_id\}\/revisions"\)/)
  assert.match(server, /base_revision must be the current ready revision/)
  assert.match(server, /parent_revision=base\.revision/)
  assert.match(server, /_run_revision_thread/)
  assert.match(server, /current_run\.update\(\{[\s\S]*?"state": "REVISING"/)
  assert.match(server, /latest = max\(ready, key=lambda item: item\.revision\)/)
  assert.match(revision, /apply_line_replace_patch/)
  assert.match(revision, /do_not_rewrite_other_sections/)
  assert.match(revision, /run_quality_gate\(/)
})
