# Document Export and Agent Tools Roadmap

## Context

Academic Pipeline Engine currently generates document text and can render DOCX output, but the workflow needs stricter boundaries:

- Draft generation should not immediately create export artifacts.
- DOCX export should be an explicit user action.
- Quality checks should catch Markdown artifacts, broken formulas, empty sections, layout defects, and conversion problems.
- Visual verification through rendered PNG pages should be available when the reviewer model supports image input.
- Agents should edit document fragments through constrained tools, not by freely rewriting the whole document.

The intended direction is similar to IDE-style agent tooling used by coding agents such as OpenCode, but adapted to document editing instead of source-code editing.

Reference projects:

- OpenCode site: https://opencode.ai/
- OpenCode repository: https://github.com/anomalyco/opencode

OpenCode is MIT-licensed at the time of review, so ideas and compatible code can be adapted if license terms and attribution are preserved.

## Decisions

### 1. Export Is Explicit

The pipeline should separate draft generation from artifact export.

Current intended stages:

1. Generate draft content.
2. Review text content.
3. Store draft state in the application.
4. Wait for the user to press `Export DOCX`.
5. Render DOCX.
6. Convert DOCX to PNG/PDF through LibreOffice/soffice.
7. Run structural and visual export QA.
8. Apply safe corrections if QA finds fixable issues.
9. Publish the final DOCX in the export directory.

This prevents unnecessary DOCX creation during every generation run and gives export a dedicated quality gate.

### 2. LibreOffice Is an Optional Runtime Dependency

LibreOffice/soffice should not be assumed to exist on every machine.

The app should detect it in this order:

1. `LIBREOFFICE_PATH` environment variable.
2. `soffice` / `libreoffice` from `PATH`.
3. Known OS-specific install locations:
   - Windows: `C:\Program Files\LibreOffice\program\soffice.exe`
   - macOS: `/Applications/LibreOffice.app/Contents/MacOS/soffice`
   - Linux: `/usr/bin/soffice`, `/usr/bin/libreoffice`, `/snap/bin/libreoffice`

If missing, the app should show actionable install guidance instead of failing silently.

Recommended install helpers:

- Windows: `winget install TheDocumentFoundation.LibreOffice`
- macOS: `brew install --cask libreoffice`
- Ubuntu/Debian: `sudo apt install libreoffice`
- Fedora: `sudo dnf install libreoffice`
- Docker: install LibreOffice in the image.

Bundling LibreOffice installers directly into the repository is not recommended because installers are large, OS-specific, architecture-specific, and become stale. If automatic downloads are later added, they must use official URLs and checksum verification.

### 3. Visual QA Is Capability-Gated

PNG page verification should be used only when all requirements are met:

- LibreOffice/soffice is available.
- DOCX successfully renders to PNG pages.
- The reviewer model has image/vision capability enabled.

This should be configured explicitly first:

```yaml
agents:
  reviewer:
    capabilities:
      document_tools: true
      vision: false
      patch_tools: false
```

Later, provider metadata can be used to auto-detect capabilities, but explicit config is the safer initial implementation.

2026-06-17 update: the safer near-term design is a separate export vision QA
layer, not the main reviewer loop. The reviewer remains responsible for content,
contract, and consistency checks before export. Export vision QA inspects rendered
DOCX/PDF pages after export and reports renderer/conversion defects. This avoids
sending renderer bugs back to the writer/reviewer loop, where text agents would
try to fix problems they did not cause.

The current validated shape is:

```yaml
export_qa:
  enabled: true
  auto_repair_enabled: false
  warnings_log_enabled: true
  provider: zen
  model: mimo-v2.5-free
  temperature: 0.1
```

`auto_repair_enabled=false` means export QA still runs and records reports, but
must not mutate the artifact or trigger repair passes. This is the default until
the repair protocol, UI notifications, warning log viewer, and documentation are
implemented end to end.

If vision is unavailable, the system should still run structural QA and log:

```text
Visual QA skipped: reviewer vision capability is disabled.
```

For the separate export QA layer, the equivalent log should be:

```text
Export vision QA skipped: provider/model or rendered page images are unavailable.
```

### 4. Agent Edits Must Use Document Tools

Agents should not be trusted to return a full rewritten document when the user asks to edit only a selected fragment.

Instead, editing must happen through constrained tool calls. The backend applies the patch, not the model.

Required tool contracts:

```text
read_document()
read_section(section_id)
read_selection(section_id, start, end)
replace_selection(section_id, start, end, expected_hash, replacement)
replace_section(section_id, expected_hash, replacement)
insert_after(section_id, anchor_hash, text)
validate_markdown()
render_docx()
render_png_pages()
inspect_export_artifacts()
```

The most important tool is `replace_selection`.

Example:

```json
{
  "tool": "replace_selection",
  "section_id": "calculation",
  "start": 1204,
  "end": 1580,
  "expected_hash": "abc123",
  "replacement": "..."
}
```

The backend must verify that the selected range still matches `expected_hash`. If the text changed after selection, the patch is rejected and the user must refresh the selection.

This prevents the agent from accidentally overwriting unrelated text.

### 5. Regeneration With Clarifications

The UI should support `Regenerate with instructions`.

The user must provide clarification text. Empty clarification should not be accepted.

Supported scopes:

- Entire document.
- Single section.
- Selected text range.

For selected text, the model returns only replacement text. It must not return the whole section or whole document.

For section-level regeneration, use `replace_section`.

For whole-document regeneration, use a separate explicit mode such as `rewrite_document`, because it has a larger blast radius.

Prompt context should include:

- Original user prompt.
- Current document or current section.
- Selected text if applicable.
- Context before and after the selected text.
- User clarification.
- Strict instruction to preserve Markdown structure and LaTeX formulas.

### 6. Reviewer Tools Are Mostly Read-Only

Reviewer should not directly mutate the document except through an approved fix loop.

Initial reviewer tools:

```text
read_document()
read_section(section_id)
validate_markdown()
render_png_pages()
inspect_png_page(page_number)
report_issue(range, severity, reason)
approve()
reject(reason)
```

If a fix is needed, the reviewer reports issues and the orchestrator asks the writer/fixer agent to produce constrained replacements through `replace_selection` or `replace_section`.

## Export QA Checks

Structural checks should run for every export:

- All required sections exist.
- No raw Markdown heading markers remain in body text where they should not.
- No visible `**bold**`, `*italic*`, `$...$`, or `$$...$$` artifacts remain in DOCX text.
- LaTeX delimiters are balanced before rendering.
- Tables are parsed as real Word tables.
- Empty sections are detected.
- Output path is inside the configured export directory.

Visual checks should run when possible:

- DOCX renders to PNG pages.
- Page count is non-zero.
- No conversion failure occurred.
- Multimodal reviewer inspects pages for visible layout defects:
- Export vision QA inspects pages for visible layout defects:
  - clipped text;
  - overlapping content;
  - broken tables;
  - missing formulas;
  - awkward spacing;
  - unreadable contrast;
  - visible Markdown artifacts.

Validated smoke behavior:

- `scripts/export_vision_qa_smoke_runner.py --provider zen --model mimo-v2.5-free`
  detected a synthetic broken export page with raw Markdown link, table, and code
  fence syntax and classified it as `conversion_issue`.
- `scripts/export_vision_qa_smoke_runner.py --provider zen --model mimo-v2.5-free --clean`
  passed a clean synthetic page with no findings.
- Smoke notes are recorded in `dev_docs/EXPORT_VISION_QA_SMOKE_NOTES.md`; raw
  JSONL/image artifacts are under ignored `exports/_smoke_export_vision_qa/`.

Integration is intentionally deferred. Wiring this into the live export endpoint
would require coordinated updates to pipeline behavior, UI warning surfaces,
QA warning persistence, documentation, and landing/public docs. The current code
keeps the runner and tests as proof that the approach works without changing the
main export path.

## Suggested Implementation Order

1. Add LibreOffice discovery utility.
2. Add prerequisite check endpoint, for example `GET /api/export/prerequisites`.
3. Split draft generation from DOCX export.
4. Add `POST /api/export/docx`.
5. Add structural export QA.
6. Add PNG render step using discovered `soffice`.
7. Add capability-gated visual QA in report-only mode.
8. Add document tool protocol for safe edits.
9. Add UI action: regenerate with clarification.
10. Add selected-text refine workflow.
11. Add export QA warning log modal and JSONL persistence.
12. Add optional export QA auto-repair behind `export_qa.auto_repair_enabled`.

## Non-Goals For The First Pass

- Do not bundle LibreOffice installers in the repository.
- Do not require a vision model for export.
- Do not let agents directly overwrite full documents for selected-text edits.
- Do not let export vision QA rewrite document content.
- Do not trigger writer/reviewer loops for renderer-only export defects.
- Do not add PostgreSQL/MongoDB until the document/session/history model is clearer.

## Open Questions

- Should document state be stored as plain JSON first, then moved to SQL later?
- Should visual QA be a reviewer responsibility or a separate `ExportVerifier` agent?
- Should the final export fixer be the writer agent with tools, or a separate constrained formatter agent?
- Should history metadata stay in JSON under `exports/_metadata` for now, or move to a lightweight SQLite database before PostgreSQL/MongoDB?
