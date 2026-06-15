# Bug Report: Patch Revision Format and Section Scope Loss

Date: 2026-06-15
Status: Fixed in current working tree

## Summary

During reviewer-driven revision, the writer sometimes failed to return valid line-based `REPLACE` blocks. The orchestrator then fell back to full-section revision. In that fallback path, the writer could return more than the current section, effectively collapsing multiple document sections into one `context[section.name]` entry.

This was observed in a run where patch revision failed with:

```text
Patch revision failed for section introduction: No REPLACE blocks found.
Falling back to full-section revision.
```

The user also observed that, after fallback, the agent appeared to delete section boundaries and try to fit all sections into one rewritten section.

## User-Visible Symptoms

- Reviewer rejects a draft and sends section or general feedback.
- Writer revision does not produce parseable `REPLACE` blocks.
- Logs show `No REPLACE blocks found`.
- Full-section fallback starts.
- The updated current section may contain content from other sections.
- Later review can see duplicated introductions, duplicated main content, or a structurally incoherent document.

## Root Causes

### 1. Self-critique could break machine-readable patch output

`WriterAgent.process()` always passed writer output through `run_self_critique()` when self-critique was enabled. The self-critique prompt was designed for prose repair and did not preserve the machine-readable patch contract.

For patch revision tasks, this meant a valid or nearly valid patch could be rewritten into ordinary Markdown text before reaching `apply_line_replace_patch()`.

Affected files:

- `academic_pe/agents/writer.py`
- `academic_pe/agents/self_critique.py`
- `academic_pe/core/section_patch.py`

### 2. Patch parser was too fragile for common LLM wrappers

`apply_line_replace_patch()` only accepted a narrow block format. Typical model wrappers such as "Here is the patch:" or markdown fences caused failures even when a valid `REPLACE` block was present.

Affected file:

- `academic_pe/core/section_patch.py`

### 3. Full-section fallback had no section-scope guard

When patch revision failed, the orchestrator requested final corrected Markdown for the current section. The context included previous and later sections for continuity, but the returned fallback text was written directly to the current section without verifying that it contained only that section.

If the model treated the context as editable material, it could return a full document. The backend would then store the full document inside one section.

Affected files:

- `academic_pe/core/orchestrator.py`
- `academic_pe/core/prompting.py`

## Fixes Applied

### Patch-format protection in self-critique

`run_self_critique()` now detects patch revision tasks. For those tasks:

- a valid repaired patch is accepted;
- if the repaired output breaks patch format but the original draft patch was valid, the original patch is preserved;
- the skipped reason is recorded as `invalid_patch_repair`;
- the self-critique prompt includes explicit patch protocol rules.

### More tolerant patch application

`section_patch.py` now:

- strips markdown code fences around patch responses;
- can validate patch-like responses with wrapper text;
- applies valid `REPLACE` blocks even if harmless wrapper prose surrounds them;
- keeps strict parsing available for direct parser tests.

### Clearer writer prompt wording

The writer GREP-tool guidance no longer mentions the old `SEARCH/REPLACE` wording. It now says `REPLACE blocks`, matching the actual parser contract.

### Section-scope guard for fallback and self-verification

`orchestrator.py` now includes `isolate_current_section_revision()`.

The guard:

- detects configured section headings in full-section fallback responses;
- recognizes common aliases for generated section names such as `introduction`, `main_part`, and `conclusion`;
- extracts the current section if the model returned a full document with clear boundaries;
- trims appended later sections when safe;
- rejects ambiguous multi-section responses instead of writing them into one section;
- retries fallback/self-verification with explicit scope feedback.

### Prompt hardening

Revision and verification prompts now state that other sections in context are read-only reference material and must not be included or rewritten in the output.

## Regression Tests Added

Added tests cover:

- patch application with common LLM wrapper text;
- patch response validation for fenced blocks and `NO_CHANGES`;
- self-critique preserving a valid patch when the critic breaks the format;
- self-critique accepting a valid repaired patch;
- extracting the current section from a full-document fallback response;
- trimming appended later sections;
- rejecting ambiguous multi-section fallback output.

Relevant tests:

- `tests/test_section_patch.py`
- `tests/test_self_critique.py`
- `tests/test_orchestrator.py`

## Verification

Full test suite passed:

```text
.venv\Scripts\python.exe -m pytest
349 passed
```

## Operational Notes

If this class of bug reappears, inspect warning logs for:

```text
Raw patch preview
Fallback revision ... returned invalid section scope
Self-verification ... returned invalid section scope
```

These messages should reveal whether the model returned ordinary prose instead of patch blocks, or returned multiple sections where only one section was allowed.

## Remaining Considerations

- The line-based patch format is still prompt-driven. A future improvement could expose a stricter structured tool call or JSON schema for line edits.
- The alias list for section headings is intentionally small. If new templates use different generated section names, add aliases near `_SECTION_NAME_ALIASES`.
- General reviewer feedback is still distributed to all sections. That is useful for cross-section issues, but it can push the writer toward broad rewrites. The current scope guard prevents destructive writes, but reviewer-to-section routing could be made smarter later.
