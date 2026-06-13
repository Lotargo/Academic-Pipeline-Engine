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

Status: `[ ] Planned`

Objective: Allow uploading reference files or previous works to extend or align new pipeline generations.

Tasks:
- [ ] Create file upload component in the UI workspace panel supporting PDF, DOCX, and MD.
- [ ] Integrate **Mistral OCR API** client in the backend to parse uploaded documents into clean Markdown.
- [ ] Add a visual list of active attachments in the UI.
- [ ] **Token Guardrail**:
  - [ ] Add `tiktoken` dependency in backend (`o200k_base` encoding).
  - [ ] Measure the token length of OCR-processed Markdown.
  - [ ] Make the token limit configurable (stored in the application configuration e.g. `config/agents.yaml`, default 20,000 tokens) to easily increase/decrease it.
  - [ ] Reject files exceeding the configured token limit with a clear validation message.
- [ ] Inject parsed reference documents into the Planner context as background material/continuity source.

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
