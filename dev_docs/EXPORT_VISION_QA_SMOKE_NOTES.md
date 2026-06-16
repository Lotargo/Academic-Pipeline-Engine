## 2026-06-17T05:20:51 - broken_export_visual
- Provider: `mock`
- Model: `mock`
- Image: `F:\projects\Academic-Pipeline-Engine\exports\_smoke_export_vision_qa\20260617_052050\broken_export_visual\page-1.png`
- Status: `passed`
- Summary: Mock vision QA inspected 1 page image(s).

## 2026-06-17T05:21:30 - broken_export_visual
- Provider: `zen`
- Model: `mimo-v2.5-free`
- Image: `F:\projects\Academic-Pipeline-Engine\exports\_smoke_export_vision_qa\20260617_052103\broken_export_visual\page-1.png`
- Status: `failed`
- Summary: Page 1 displays unrendered Markdown syntax, including a link, table, and code block, indicating a conversion failure.
- Finding: `error` `conversion_issue` page=1: Raw Markdown link syntax '[Contributor Covenant] (https://example.test/code_of_conduct)' is visible instead of a rendered hyperlink.
- Finding: `error` `conversion_issue` page=1: Raw Markdown table syntax '| Parameter | Type | Description |' and '|---|---|---|' is displayed as plain text, with no table rendered.
- Finding: `error` `conversion_issue` page=1: Raw Markdown code block start '```python' is visible, but the code block is not rendered or closed.

## 2026-06-17T05:21:57 - clean_export_visual
- Provider: `zen`
- Model: `mimo-v2.5-free`
- Image: `F:\projects\Academic-Pipeline-Engine\exports\_smoke_export_vision_qa\20260617_052141\clean_export_visual\page-1.png`
- Status: `passed`
- Summary: Page 1 rendered cleanly with no visual defects observed.

## Integration Decision

- Status: validated but deferred.
- The smoke test proves that `zen` + `mimo-v2.5-free` can distinguish a synthetic broken export page from a clean page.
- Do not wire this into the live export endpoint yet.
- Keep the current implementation as a report-only QA Vision proof and smoke runner.
- Future integration must update the export pipeline, QA warning logs, notification modal, settings UI semantics, public docs, and landing/docs references together.
- Default behavior should remain `export_qa.auto_repair_enabled=false`: QA may report, but must not repair or trigger writer/reviewer loops.
- Renderer/conversion defects should be owned by renderer/export QA repair logic, not by writer or reviewer agents.
