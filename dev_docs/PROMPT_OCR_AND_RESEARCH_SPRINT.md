# Prompt Enhancement, Mistral OCR Attachments & Web Research Sprint

Date: 2026-06-13  
Status: In progress - prompt enhancement and export/archive hardening completed; OCR attachments and Researcher remain planned.
Scope: Prompt engineering helper, attachment uploads, Mistral OCR pipeline, token limits, and optional Researcher search agent.

## Sprint Goal

Enhance the pipeline's intelligence and input flexibility by introducing:
1. An LLM-powered prompt enhancer to refine user prompts before generation.
2. File attachments processed via Mistral OCR to allow continuing/analyzing external documents, with a 20k token safety limit.
3. An optional web-search-based Researcher agent integrated directly into the FSM Planning phase to source current data and inject citations.

## Status Legend

- `[x] Completed` (выполнено)
- `[~] In progress` (в работе)
- `[ ] Planned / Pending` (ожидает)
- `[!] Needs design decision` (требует обсуждения)

---

## Prerequisite / Baseline Cleanups

- [x] Automatically clean up empty run directories on startup.
- [x] Delete run directories on pipeline cancellation or execution failure.
- [x] Clean up empty run directories on successful completions when no plots are generated.
- [x] Delete the entire run directory recursively (containing docx, plots, and QA outputs) when deleting a history item from the UI.
- [x] Fixed console panel to only be toggleable manually (removed auto-open on task start).
- [x] Added `config/agents.yaml` and `ui/next-env.d.ts` to `.gitignore` and removed them from the Git index to avoid noisy local/runtime changes.

---

## Completed Additional Work: Export, Archive & UI Hardening

Status: `[x] Completed`

These items were completed during the sprint even though they were not part of the original OCR/research plan. They are important for later README/docs updates because they materially changed the product workflow.

### DOCX Rendering Quality

- [x] Fixed DOCX bibliography/list numbering bug where rendered numbered lists could continue from a previous sequence and start at `11` instead of `1`.
- [x] Added regression coverage for numbered list rendering.

### Dynamic Export Filenames

- [x] Added sanitized document-title-based filenames instead of always exporting as `Final_Academic_Paper.docx`.
- [x] Preserved normal word spaces in generated filenames.
- [x] Sanitized unsupported filename characters for Windows and other operating systems.
- [x] Added tests for filename sanitization and export filename resolution.

### PDF Export

- [x] Added local PDF export through LibreOffice/soffice conversion from the high-quality DOCX renderer.
- [x] Added `/api/export/pdf` backend endpoint.
- [x] Added `/api/export/prerequisites` endpoint to report LibreOffice availability and install hints.
- [x] Updated `/api/download` to serve PDF files with the correct MIME type.
- [x] Added PDF export/download buttons in the active document and archive document UI.
- [x] Verified local LibreOffice conversion quality manually.
- [x] Added automated PDF export endpoint tests.

### Run Directory Consistency

- [x] Ensured explicit DOCX/PDF exports can target the active or archived document `run_id`.
- [x] Returned `run_id` from history metadata so archive exports save beside the original run assets.
- [x] Stored `run_id` in new history/export metadata records.
- [x] Validated `run_id` format before using it for export paths.
- [x] Added regression coverage proving PDF export saves under `exports/<run_id>`.

### Archive & Document Actions

- [x] Added visible archive and delete actions for selected documents.
- [x] Added delete support from the archived works modal.
- [x] Improved sidebar history item layout so long titles wrap/clamp and action controls stay visible.

### Export Card Layout

- [x] Fixed long export filenames wrapping over action buttons.
- [x] Kept DOCX/PDF/copy buttons inside the export card on narrow layouts.
- [x] Aligned the preview eye icon with the export status and filename block.

### Notifications

- [x] Replaced the default toast appearance with a custom two-tone Academic PE notification style.
- [x] Moved notifications lower on the right side so they no longer cover top-right workspace controls.
- [x] Increased notification width for better readability.
- [x] Added right-side slide-in/slide-out animation.

---

## Workstream 1: Prompt Enhancement Agent

Status: `[x] Completed`

Objective: Add an interactive assistant button to refine and enrich poorly formulated prompts before running the generator.

Tasks:
- [x] Reuse the `example_generator` agent for prompt enhancement (leveraging its system role as a senior academic director and prompt engineer).
- [x] Add a specific instruction manifest for the enhancement request so the agent refines a raw user topic/instruction into a technically deep academic task.
- [x] Add `/api/prompt/enhance` endpoint to send a raw prompt to the `example_generator` agent and return a structured, optimized version.
- [x] Add an "Enhance" (🪄) button next to the topic input in the UI.
- [x] Implement loading indicator and smooth replacement of the topic value with the enhanced prompt.

---

## Workstream 2: Document Attachments & Mistral OCR Integration

Status: `[~] In progress`

Objective: Allow uploading reference files or previous works to extend or align new pipeline generations.

### Continuation Mode Clarification

The attachment/OCR feature is not only a passive reference-material upload. It must also support a direct "continue this work" workflow:

- A user can take an already generated/archive document from the UI and start a continuation from it without manually downloading and re-uploading it.
- A user can also upload an external previous work through Mistral OCR and ask the pipeline to continue, expand, or adapt it.
- In continuation mode, all agents must treat the previous work as the semantic base and preserve its topic, argument chain, terminology, style, and already established structure unless the user explicitly asks to change them.
- Continuation sources must include the previous user prompt, previous instructions, previous document plan, and previous runtime template/manifest whenever available. These are required context, not optional metadata, because the agents need them to infer why the original document had its genre, structure, tone, and audience level.
- If the previous work is non-academic (for example a children's story, school narrative, informal essay, poem, or creative text), continuation must preserve that genre, narrator/voice, pacing, and audience level unless the new user request explicitly asks to convert the style.
- The pipeline must not simply append a disconnected second document. It should produce one coherent revised/continued document.
- To make the continuation coherent, agents may need to rewrite or trim terminal parts of the previous work, especially conclusions, summaries, closing transitions, and final bibliography/appendix placement.
- The Planner should detect where the previous work naturally ends, decide what must be preserved, what needs bridging/revision, and how the new user clarification continues the existing logic.
- The Writer should draft new sections as a continuation of the prior argument, not as a restart from the original topic.
- The Reviewer should check continuity: no duplicated introductions/conclusions, no contradiction with the previous work, no abrupt style shift, and no loss of the user's requested continuation details.

Tasks:
- [ ] Create file upload component in the UI workspace panel supporting PDF, DOCX, and MD.
- [x] Add UI action to continue from an existing generated/archive document directly from the document/archive controls.
- [ ] Integrate **Mistral OCR API** client in the backend to parse uploaded documents into clean Markdown.
- [ ] Add a visual list of active attachments in the UI.
- [~] Add attachment metadata distinguishing passive reference material from continuation source documents.
- [ ] **Token Guardrail**:
  - [ ] Add `tiktoken` dependency in backend (`o200k_base` encoding).
  - [ ] Measure the token length of OCR-processed Markdown.
  - [ ] Make the token limit configurable (stored in the application configuration e.g. `config/agents.yaml`, default 20,000 tokens) to easily increase/decrease it.
  - [ ] Reject files exceeding the configured token limit with a clear validation message.
- [ ] Inject parsed reference documents into the Planner context as background material/continuity source.
- [x] Update Planner prompts so continuation sources are analyzed as existing document state, including preserved content, sections to revise/trim, bridge requirements, and new continuation sections.
- [x] Update Writer prompts so generated content extends the existing document and can revise ending/transition sections instead of producing a separate standalone paper.
- [x] Update Reviewer prompts/quality checks to validate continuity, avoid duplicated endings, and ensure the resulting output reads as one coherent document.

---

## Workstream 3: Researcher Agent (DuckDuckGo + URL Parsing)

Status: `[ ] Planned`

Objective: Implement an optional Researcher agent that performs internet search and feeds citations directly into the document plan.

Tasks:
- [ ] Add an "Enable Web Search" toggle in the UI generation settings.
- [ ] Create a `ResearcherAgent` in the backend.
- [ ] **Search Anti-Blocking Guard**:
  - [ ] Implement browser request simulation by mimicking headers of a real web browser (e.g. customized User-Agent, Accept-Language, Referrer) and adding rate limits to avoid being flagged as a bot by DuckDuckGo and crawled sites.
- [ ] **Parallel Execution & File-Based Exchange**:
  - [ ] Support spawning a pool of parallel search agents, each assigned a specific search query or target URL.
  - [ ] For each search agent, write its fetched findings (crawled markdown/text, links, metadata) to a separate temporary file inside the run directory. This avoids keeping massive scraped documents in memory.
  - [ ] The Planner agent reads these files on-demand to index findings and build the document plan.
- [ ] Integrate search logic in the Planning state:
  - [ ] The Planner generates research queries and calls the Researcher.
  - [ ] The Researcher executes searches and crawls top matches.
  - [ ] The Researcher returns synthesized findings with citations/URLs back to the Planner.
- [ ] Update FSM Planning to build the outline specifically around the retrieved research data and embed the citations (links) so the writer can output them.
