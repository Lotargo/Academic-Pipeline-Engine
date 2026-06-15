# Continuation, Editing, and Document Merge Sprint

Date: 2026-06-15  
Status: In progress
Scope: Continuation semantics, in-place editing, section heading policy, source/reference merging, document assembly, and reviewer/exporter checks.

## Sprint Goal

Move continuation and revision from "generate a new document with prior context" to "apply deliberate edit operations to an existing document state".

The pipeline must be able to continue, improve, expand, or restructure a previous work without forcing the user to manually stitch the result afterward. This applies to creative writing, school assignments, technical documents, reports, RGR/coursework/thesis-style academic work, and other structured artifacts.

## Core Principle

The previous document is not just context. It is the current artifact state.

Planner should design edit intent and merge operations. Writer should produce only the required fragments or patches. Reviewer should validate continuity and structural integrity. Exporter should assemble one seamless final artifact according to the document contract.

## Problem Statement

Current continuation behavior has improved planning quality, but final output can still feel like a separate branch:

- Planner may correctly identify narrative or document logic, red flags, and next moves.
- Internal planning blocks such as exposition, development, conflict, risks, or red flags can leak into the final document as visible sections.
- Writer may draft a fresh section structure instead of merging with the existing text.
- Continuation text may appear after a completed ending, bibliography, appendix, or conclusion.
- Scientific and school documents may need updated references, numbering, formulas, tables, and cross-references, but those updates must appear seamless rather than as "added changes".

The sprint fixes this by introducing an explicit document operation layer and a richer final-structure policy.

## Status Legend

- `[x] Completed`
- `[~] In progress`
- `[ ] Planned / Pending`
- `[!] Needs design decision`

---

## What We Have Not Fully Accounted For Yet

These are the design areas that should be handled before implementation to avoid another broad refactor.

### 1. Visible Headings Versus Internal Planning Blocks

Not every planner section is a document heading.

Creative artifacts may need visible chapters, parts, dates, scene breaks, or user-mandated section titles. They should not expose internal beats like exposition, conflict analysis, red flags, or pacing notes unless the user explicitly asks for an outline.

Academic and school artifacts often require visible headings: introduction, theory, method, calculations, analysis, conclusion, references, appendices. Those headings should be preserved, generated, or renumbered according to the artifact contract.

Required concept:

```json
{
  "id": "development",
  "title": "Development",
  "semantic_role": "narrative_beat",
  "heading_policy": "internal_only"
}
```

Supported `heading_policy` values:

- `render_required`: must appear in the final document.
- `render_allowed`: may appear when compatible with the artifact and source style.
- `internal_only`: used by agents only, never rendered.
- `inherit_source`: preserve source heading behavior.
- `user_mandated`: explicitly requested by the user, do not rename or drop.

### 2. Continuation Intent Is Not One Mode

"Continue" can mean several operations. The default must be conservative.

Proposed continuation intents:

- `continue_append`: continue after the natural current endpoint.
- `bridge_and_continue`: rewrite or trim the final transition, then append continuation.
- `revise_in_place`: improve existing content without extending scope.
- `expand_section`: expand a specific section or chapter.
- `complete_missing_section`: fill a known gap in an existing required structure.
- `update_references_only`: merge bibliography/citations without changing body content.
- `restructure`: rebuild structure only when explicitly requested.

When the user clicks Continue without extra instructions, default to `continue_append` or `bridge_and_continue`, depending on whether the source has a hard ending.

### 3. Continuity Dossier

Before writing, Planner should produce a compact internal continuity dossier. This is not final document content.

For creative writing:

- current stopping point;
- unresolved plot lines;
- narrator, viewpoint, tense, pacing, and tone;
- character state and relationships;
- location/time continuity;
- motifs, symbols, and forbidden retcons;
- whether the final paragraphs need bridge revision.

For academic/school/technical documents:

- thesis/goal and current argument chain;
- definitions and terminology;
- existing section structure and numbering;
- source/citation style;
- formulas, tables, figures, variables, and labels;
- missing sections or weak sections;
- conclusion/reference/appendix placement;
- constraints from user request, course type, or template.

The dossier should be stored in metadata and optionally shown in UI as an editorial layer, but not rendered into the final document.

### 4. Merge Operations

Continuation should produce operations, not a standalone replacement document.

Initial operation vocabulary:

```json
[
  {"op": "preserve", "target": "existing_body"},
  {"op": "replace_tail", "paragraphs": 2, "purpose": "smooth_bridge"},
  {"op": "append_after", "target": "last_body_section", "content_role": "continuation"},
  {"op": "insert_before", "target": "references", "content_role": "new_body_content"},
  {"op": "update_references", "mode": "dedupe_and_merge"}
]
```

Potential operations:

- `preserve`: keep source content unchanged.
- `replace_range`: replace a known paragraph/line/section range.
- `replace_tail`: revise the last N paragraphs to remove a terminal ending.
- `append_after`: add content after a target anchor.
- `insert_before`: add content before references, appendix, or final metadata sections.
- `expand_section`: add material inside an existing section.
- `rename_heading`: only when allowed by heading policy.
- `renumber_sections`: update visible numbering.
- `update_cross_references`: update figure/table/formula/section references.
- `update_references`: deduplicate and merge bibliography.
- `move_terminal_sections_to_end`: ensure references/appendices remain terminal.

### 5. Bibliography And Source Registry

References should not be treated as ordinary body text.

Required concept: a `reference_registry` extracted from the source and updated during editing.

Responsibilities:

- preserve existing sources;
- infer citation style when possible;
- detect new claims that require support when the artifact contract requires citations;
- add new sources only when allowed/requested/required;
- deduplicate sources;
- update in-text citations and final bibliography together;
- keep references as one seamless final list.

Important rule:

If the source already has a references section, body continuation should usually be inserted before it, then references should be rebuilt at the end.

No final output should say "new sources added" unless the user requested an editorial changelog.

### 6. Terminal Sections

Some sections are terminal and must remain at the end:

- references / bibliography / works cited;
- appendices;
- glossary, if required by contract;
- author notes, if user-mandated;
- generated export metadata, if any.

Continuation must not append new body content after terminal sections.

### 7. Cross-References, Numbering, And Labels

Scientific and technical documents need structural consistency:

- section numbers;
- table numbers;
- figure numbers;
- formula numbers;
- appendix labels;
- "see section/table/figure" references;
- bibliography numbering.

Reviewer must reject outputs that introduce broken references, duplicate numbering, or body content after terminal sections.

### 8. Style Preservation Is Multi-Dimensional

"Preserve style" is not only prose tone.

The preservation contract should include:

- language and register;
- narrator/voice/viewpoint;
- tense;
- paragraph length and density;
- heading style;
- citation style;
- formula style;
- table style;
- markdown/docx rendering conventions;
- terminology glossary;
- source audience level.

### 9. Editable Diffs And User Trust

The user should be able to see what changed.

The final document should be seamless, but the UI can show an editorial diff layer:

- preserved content;
- replaced tail paragraphs;
- newly inserted continuation;
- updated references;
- red flags resolved or still open.

This diff layer belongs in UI/metadata, not in the exported document.

### 10. Backward Compatibility

Existing history items may not have operation metadata, source registries, or heading policies.

Fallback behavior:

- infer visible headings from current runtime template and rendered source;
- infer terminal sections by heading names;
- infer references from common heading aliases;
- default unknown planner blocks to `internal_only` unless they were present in the source or user prompt;
- preserve current generation path for brand-new documents.

---

## Proposed Architecture

### Runtime Objects

Add or derive these runtime structures:

```text
DocumentState
  source_sections
  rendered_body
  terminal_sections
  headings
  reference_registry
  continuity_dossier
  style_profile
  runtime_manifest

EditPlan
  intent
  operations
  heading_policies
  red_flags
  reference_policy
  acceptance_checks

MergePatch
  operation_outputs
  inserted_content
  replaced_ranges
  updated_references
  reviewer_notes
```

### Agent Responsibilities

Planner:

- infer continuation intent;
- extract continuity dossier;
- classify headings and terminal sections;
- choose merge operations;
- decide whether references need update;
- mark internal-only versus renderable blocks.

Writer:

- write only required operation payloads;
- preserve source voice and structure;
- avoid restarting the artifact;
- avoid adding editorial notes to final content;
- use patch/range output when editing existing content.

Reviewer:

- validate operation fit;
- check continuity;
- check no internal planning labels leaked;
- check terminal sections remain terminal;
- check bibliography/citations are coherent;
- check cross-references and numbering.

Exporter/assembler:

- apply merge operations deterministically;
- render only blocks with renderable heading policy;
- rebuild references at the correct terminal location;
- preserve final document as one artifact.

---

## Workstream 1: Heading And Section Policy

Status: `[~] In progress`

Objective: Separate internal planning structure from final document headings.

Tasks:

- [x] Add heading policy fields to runtime template/section structures.
- [x] Add semantic roles such as `chapter`, `academic_section`, `narrative_beat`, `editorial_note`, `reference_section`, `appendix`, `glossary`.
- [x] Update planner prompt/schema so it labels internal-only blocks explicitly.
- [x] Update writer prompt so it never renders `internal_only` titles.
- [x] Update exporter/preview to respect heading policy.
- [x] Add regression tests where `exposition/development/red_flags` are internal but user-mandated chapter titles are rendered.

Definition of done:

- Internal planning blocks do not appear in final documents.
- User-mandated and contract-required headings still render.
- Source heading style can be inherited during continuation.

---

## Workstream 2: Continuation Intent Resolver

Status: `[~] In progress`

Objective: Infer the editing operation the user likely wants.

Tasks:

- [x] Add continuation intent enum.
- [x] Detect no-instruction Continue as `continue_append` or `bridge_and_continue`.
- [x] Detect requests like "improve", "rewrite", "expand chapter 2", "add bibliography", "finish conclusion".
- [x] Store intent in runtime metadata.
- [~] Add UI display for inferred intent with override later if needed.
- [x] Add tests for creative, school, technical, and academic prompts.

Definition of done:

- Continue without instructions does not create a separate standalone artifact.
- Improve/revise requests do not accidentally append new chapters.
- Explicit restructure requests remain possible.

---

## Workstream 3: Document State Extraction

Status: `[~] In progress`

Objective: Convert the existing generated/archive/uploaded document into a structured state object before planning.

Tasks:

- [ ] Extract heading tree from Markdown/context sections.
- [x] Identify terminal sections.
- [x] Identify source section order and visible titles.
- [ ] Extract style profile.
- [ ] Extract reference registry when references exist.
- [ ] Extract table/figure/formula labels when present.
- [ ] Store a compact continuity dossier in metadata.

Definition of done:

- Planner receives structured document state, not just raw text context.
- Continuation can target anchors before references/appendices.
- Existing source headings and references are preserved.

---

## Workstream 4: Merge Operation Schema

Status: `[~] In progress`

Objective: Introduce deterministic edit operations between planning and writing.

Tasks:

- [x] Define Pydantic models for edit operations.
- [~] Add validation for operation targets.
- [x] Add operation application logic.
- [x] Support replacing tail paragraphs for seamless bridges.
- [x] Support inserting body content before terminal sections.
- [x] Support updating references as a terminal operation.
- [x] Store operations in run metadata for audit/UI diff.

Definition of done:

- Continuation output is assembled from source plus operations.
- Writer no longer needs to return an entire rewritten document for common continuation.
- User can inspect operation summary in UI.

---

## Workstream 5: Reference Registry And Bibliography Merge

Status: `[ ] Planned`

Objective: Make citation and bibliography updates seamless for educational and scientific artifacts.

Tasks:

- [ ] Detect bibliography/reference sections by aliases and source style.
- [ ] Parse simple numbered, bullet, and author-year references.
- [ ] Preserve source citation style where possible.
- [ ] Add source registry to runtime metadata.
- [ ] Update researcher/planner to add sources through registry, not raw final prose.
- [ ] Deduplicate references.
- [ ] Rebuild final bibliography as one section.
- [ ] Ensure body continuation is inserted before references.
- [ ] Add tests for adding a new source during continuation without adding "new references" labels.

Definition of done:

- Existing references are not lost.
- New sources are merged into one final bibliography.
- In-text citations and bibliography stay consistent.

---

## Workstream 6: Reviewer Continuity Gate

Status: `[ ] Planned`

Objective: Add quality checks that specifically catch disconnected continuation and leaked planning structure.

Tasks:

- [ ] Reject duplicated introductions/conclusions when not requested.
- [ ] Reject body content after terminal references/appendices.
- [ ] Reject visible internal planning labels.
- [ ] Reject abrupt style, narrator, or register shifts.
- [ ] Reject broken numbering and cross-references.
- [ ] Reject bibliography mismatch when citations are required.
- [ ] Add line/section-aware feedback so patch revision can fix only affected ranges.

Definition of done:

- Reviewer catches branch-like continuation.
- Reviewer gives actionable section/range feedback.
- Fix loop preserves merge operation protocol.

---

## Workstream 7: UI Continuation Controls And Diff Layer

Status: `[ ] Planned`

Objective: Make continuation/editing behavior visible and correctable without exposing internal clutter in the final document.

Tasks:

- [ ] Show inferred continuation intent before generation.
- [ ] Show source summary/continuity dossier in a collapsible editorial panel.
- [ ] Show red flags as UI metadata, not final content.
- [ ] Show operation summary after generation.
- [ ] Add "view changes" mode for preserved/replaced/inserted/reference-updated content.
- [ ] Add optional user override for intent and target section.

Definition of done:

- User can understand why the continuation changed specific parts.
- Final export remains clean.
- Manual stitching burden is reduced.

---

## Workstream 8: Export And Preview Assembly

Status: `[ ] Planned`

Objective: Ensure preview and exported DOCX/PDF render the same assembled final artifact.

Tasks:

- [ ] Route preview through the same assembly logic as export.
- [ ] Hide internal-only sections in preview/export.
- [ ] Keep references/appendices at the end.
- [ ] Preserve heading levels and numbering.
- [ ] Preserve source title/author metadata unless user changes it.
- [ ] Add export tests for continuation with bibliography and appendices.

Definition of done:

- Preview matches exported document.
- Internal planning artifacts never leak into DOCX/PDF.
- Terminal sections remain terminal across formats.

---

## Workstream 9: Real Pipeline Smoke Bench Gate

Status: `[ ] Planned`

Objective: Require a short real-model pipeline check after broad continuation/editing changes, without turning it into a full benchmark suite.

This gate is meant to catch behavioral imbalance, prompt drift, disconnected continuation, section leakage, broken reference placement, and provider/config integration issues that unit tests and mock providers cannot reliably reveal.

Rules:

- [ ] Run this smoke bench after any large change touching Planner, Writer, Reviewer, prompt manifests, continuation metadata, merge operations, export assembly, reference handling, or UI continuation flow.
- [ ] Use the locally configured real providers, keys, and models already present in the developer environment. Do not commit keys, copy secrets into logs, or replace this with mock-provider results.
- [ ] Keep the suite short: target 4-6 scenarios, each with a clear pass/fail rubric.
- [ ] Record only concise findings: model/provider used, scenario id, pass/fail, elapsed time, major issue if failed, and follow-up link/task if needed.
- [ ] Do not compare models against each other and do not optimize for leaderboard scores. This is a smoke bench, not benchmark testing.
- [ ] If real keys/models are unavailable in a fresh environment, mark the gate blocked and do not claim the sprint behavior is validated end-to-end.

Required scenarios:

- [ ] **Creative continuation**: generate or reuse a short story with visible user-facing parts, then Continue with no extra instructions. Check that continuation reads as the same story, does not restart, does not expose internal beats such as exposition/development/red flags, and preserves voice/pacing.
- [ ] **Creative bridge**: continue a story with a closed ending. Check that the pipeline trims or bridges terminal paragraphs instead of appending a disconnected branch.
- [ ] **School revision**: improve an existing school composition. Check that the result revises in place, preserves age/register, and does not append a new essay.
- [ ] **Academic/RGR continuation with references**: continue a structured academic or calculation-heavy document that already has references. Check that new body content appears before references, bibliography remains terminal, and new sources are merged seamlessly if introduced.
- [ ] **Technical document continuation**: continue a README/report-like artifact. Check that practical headings are preserved and no academic-paper structure is forced.

Pass/fail rubric:

- [ ] No visible internal planning labels in final preview/export.
- [ ] No duplicated introduction, conclusion, title page, or bibliography unless explicitly requested.
- [ ] No body content after references/appendices.
- [ ] Continuation preserves source genre, voice/register, heading style, and terminology.
- [ ] Merge operation metadata matches what happened in the final artifact.
- [ ] Reviewer feedback is actionable when the gate fails.
- [ ] Preview and exported DOCX/PDF represent the same assembled artifact.

Suggested run note format:

```text
Date:
Commit/branch:
Config snapshot: provider/model names only, no keys
Scenario:
Result: PASS/FAIL
Elapsed:
Observed imbalance:
Follow-up:
```

Definition of done:

- Real-model smoke bench has been run for the current broad change set.
- Failures either block completion or have explicit follow-up tasks.
- Results are short enough to stay useful and safe to store in dev notes.

---

## Acceptance Scenarios

### Creative Story: Continue Without Instructions

Input: generated story with visible parts "Opening", "Descent", "Disappearance"; user clicks Continue with no extra text.

Expected:

- Planner infers `bridge_and_continue` if the ending is closed, otherwise `continue_append`.
- Internal beats do not appear as headings.
- Existing visible part/chapter style is preserved.
- Last paragraphs may be lightly bridged.
- Continuation reads as the same story, not a spin-off.

### School Essay: Improve Existing Work

Input: school composition with introduction/body/conclusion; user asks to improve style.

Expected:

- Intent is `revise_in_place`.
- No new essay is appended.
- Student-level voice is preserved.
- Headings remain only if source had them or assignment requires them.

### RGR/Coursework: Continue Before References

Input: technical academic document with calculations and a bibliography; user asks to add the next analysis section.

Expected:

- New body content is inserted before references.
- Formula/table numbering remains consistent.
- New sources are merged into the same bibliography if needed.
- No "added section" editorial wording appears.

### Thesis/Diploma: Expand Chapter

Input: thesis draft with numbered chapters and references; user asks to expand chapter 2.

Expected:

- Intent is `expand_section`.
- Only chapter 2 receives new content unless cross-reference/reference updates are required.
- Numbering and bibliography remain coherent.
- Abstract/introduction/conclusion are not rewritten unless necessary.

---

## Test Plan

Backend tests:

- heading policy rendering and internal-only filtering;
- continuation intent detection;
- document state extraction from generated history metadata;
- terminal section detection;
- edit operation validation and application;
- bibliography merge and deduplication;
- reviewer gate prompts include continuity and terminal-section checks;
- exporter renders assembled document, not raw planner structure.

Frontend tests/manual checks:

- Continue button with no instructions;
- intent display and editorial panel;
- red flags shown in UI but not exported;
- preview/export parity;
- continuation from archived document;
- continuation with references and appendices.

Golden tests:

- creative story continuation does not show "exposition/development/red flags";
- academic continuation inserts before bibliography;
- school essay improvement revises in place;
- technical README continuation preserves README headings.

Mandatory real pipeline smoke bench:

- Run the Workstream 9 scenarios on the configured real providers/models after broad changes.
- Store concise pass/fail notes in a local sprint note or PR summary.
- Treat leaked internal headings, disconnected continuation, terminal-section violations, and broken bibliography merges as blocking failures.

---

## Implementation Order

Recommended order:

1. Add heading policy and internal-only filtering.
2. Add continuation intent resolver.
3. Add document state extraction and terminal-section detection.
4. Add merge operation schema and deterministic assembler.
5. Add reference registry and bibliography merge.
6. Strengthen reviewer gate.
7. Add UI intent/diff/editorial panels.
8. Align preview/export with assembler.
9. Run the real pipeline smoke bench gate before marking broad behavior complete.

This order gives early UX value while avoiding a large all-at-once rewrite.

## Out Of Scope For This Sprint

- Full semantic citation verification against external databases.
- Full DOCX round-trip editing with exact Word style preservation.
- Complex legal/medical source compliance.
- Multi-author change tracking comparable to Microsoft Word Track Changes.
- Replacing the existing template library system.

## Open Design Questions

- Should the UI allow users to edit the inferred continuation intent before running, or only after a low-confidence warning?
- How much of the continuity dossier should be visible by default?
- Should operation application happen before or after section-level reviewer loops?
- Should bibliography parsing be rule-first with LLM repair, or LLM-first with rule validation?
- How should uploaded OCR documents map to source sections when headings are noisy?
- Where should real smoke bench notes live: local-only run notes, PR summaries, or a sanitized dev_docs log?
