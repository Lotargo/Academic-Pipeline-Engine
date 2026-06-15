# Prompt Enhancement, Mistral OCR Attachments & Web Research Sprint

Date: 2026-06-13  
Status: In progress - prompt enhancement and export/archive hardening completed; OCR attachments and Researcher partially implemented, with role-boundary audit fixes remaining.
Scope: Prompt engineering helper, attachment uploads, Mistral OCR pipeline, token limits, and optional Researcher search agent.

## Sprint Goal

Enhance the pipeline's intelligence and input flexibility by introducing:
1. An LLM-powered prompt enhancer to refine user prompts before generation.
2. File attachments processed via Mistral OCR to allow continuing/analyzing external documents, with a 20k token safety limit.
3. An optional web-search-based Researcher agent integrated directly into the FSM Planning phase to source current data and inject citations.

## Required Role Boundary / Research Activation Contract

This contract supersedes any earlier ambiguous wording about Researcher or Writer responsibilities.

- Standard pipeline behavior must remain unchanged unless the user explicitly enables the web-search activator (`web_search_enabled` / "Enable Web Search").
- When the activator is off, no new web-search/research agent should run, no search queries should be generated, and the pipeline should behave as the normal Planner -> Writer -> Reviewer flow.
- When the activator is on, research must be owned by the Planning phase:
  - the Planner decides what information is needed;
  - the Planner generates the search queries or target research tasks;
  - one or more Researcher workers execute those tasks and return findings with source URLs/citations;
  - the Planner uses those findings to produce the document plan and embeds only the necessary facts, source notes, and citation instructions into that plan.
- The Writer must not search, crawl, parse research sources, choose sources, or receive raw search findings as a separate research context.
- The Writer's responsibility is only to write the requested document sections from the prepared plan, continuity context, and normal drafting instructions.
- Passive reference attachments should follow the same boundary: the Planner may inspect and summarize/select relevant information, but the Writer should receive only planner-curated instructions or selected excerpts needed for drafting.
- If web search is enabled but no dedicated Planner agent is configured, the system must not silently fall back to using the Writer as the Planner/Research Director. It should either require a Planner configuration or fail clearly before starting research.

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
- [x] Create file upload component in the UI workspace panel supporting PDF, DOCX, and MD.
- [x] Add UI action to continue from an existing generated/archive document directly from the document/archive controls.
- [x] Integrate **Mistral OCR API** client in the backend to parse uploaded documents into clean Markdown.
  - Implemented: backend upload endpoint, Mistral file upload + OCR call, page Markdown merge, cleanup attempt, and local PDF/DOCX/MD fallback.
  - Verified: direct smoke test with the configured `config/secrets.json` Mistral key successfully OCR'd a generated PDF and preserved a unique marker.
- [x] Add a visual list of active attachments in the UI.
- [x] Add attachment metadata distinguishing passive reference material from continuation source documents.
- [x] **Token Guardrail**:
  - [x] Add `tiktoken` dependency in backend (`o200k_base` encoding).
  - [x] Measure the token length of OCR-processed Markdown.
  - [x] Make the token limit configurable (stored in the application configuration e.g. `config/agents.yaml`, default 20,000 tokens) to easily increase/decrease it.
  - [x] Reject files exceeding the configured token limit with a clear validation message.
- [x] Inject parsed reference documents into the Planner context as background material/continuity source.
  - Implemented: passive reference attachments are passed into the Planner prompt.
  - Implemented: raw passive reference materials are no longer sent directly to the Writer; the Planner curates the relevant information through the document plan.
- [x] Update Planner prompts so continuation sources are analyzed as existing document state, including preserved content, sections to revise/trim, bridge requirements, and new continuation sections.
- [x] Update Writer prompts so generated content extends the existing document and can revise ending/transition sections instead of producing a separate standalone paper.
- [x] Update Reviewer prompts/quality checks to validate continuity, avoid duplicated endings, and ensure the resulting output reads as one coherent document.

### Remaining Attachment/OCR Audit Fixes

- [x] Add tests for `/api/attachments/upload` success, unsupported file type, and token-limit rejection.
- [x] Add a UI affordance to choose "reference material" vs "continuation source" before upload, or make the post-upload toggle clearer.
- [ ] Confirm continuation-source uploads preserve enough previous-work metadata when available; uploaded external documents can only infer structure from Markdown unless the user provides prior prompt/instructions.

---

## Workstream 3: Researcher Agent (DuckDuckGo + URL Parsing)

Status: `[~] In progress`

Objective: Implement an optional Researcher agent that performs internet search and feeds citations directly into the document plan.

Tasks:
- [x] Add an "Enable Web Search" toggle in the UI generation settings.
- [x] Add `web_search_enabled` request plumbing from UI -> API model -> backend thread -> Orchestrator.
- [x] Create a `ResearcherAgent` in the backend.
  - Implemented: `academic_pe/agents/researcher.py` with `ResearcherAgent`, registered in the agent factory as `agent_type: researcher`.
  - Implemented: `academic_pe/core/researcher.py` remains the deterministic search/crawl implementation used by the agent.
- [~] **Search Anti-Blocking Guard**:
  - [x] Implement browser request simulation by mimicking headers of a real web browser (e.g. customized User-Agent, Accept-Language, Referrer).
  - [x] Add basic per-request delay/rate limiting.
  - [x] Add stronger timeout/error policy, retry/backoff, and tests for blocked/empty DDG result pages.
- [~] **Parallel Execution & File-Based Exchange**:
  - [x] Support spawning a pool of parallel search workers, each assigned a specific search query.
  - [x] For each search worker, write fetched findings (crawled text, links, metadata) to a separate temporary JSON file inside the run directory.
  - [x] The Planner reads compact citation-ready source briefs from these files to build the document plan.
    - Implemented: findings files are loaded into a combined Planner context string with title, URL, snippet, and bounded relevant excerpt.
- [~] Integrate search logic in the Planning state:
  - [x] The Planning state checks the web-search activator before any search work starts.
  - [x] The Planner model is used to generate research queries.
  - [x] The Researcher executes searches and crawls top matches.
  - [x] The Researcher returns compact findings with citations/URLs back to the Planner.
    - Implemented: returned findings include source titles, URLs, snippets, and bounded excerpts rather than long raw crawled previews.
- [x] Update FSM Planning to build the outline specifically around the retrieved research data and embed the citations (links) so the writer can output them.
  - Implemented: retrieved findings are injected into the Planner prompt and the Planner prompt asks for citation/link embedding.
  - Implemented: the Writer receives only the Planner-curated plan/source notes, not raw `search_findings` or raw research context.

### Remaining Researcher Audit Fixes

- [x] Enforce the activator contract with tests: when `web_search_enabled=False`, no query generation, researcher import/calls, or research files are created.
- [x] Enforce the Planner-only research contract with tests: when `web_search_enabled=True`, the system must use a dedicated Planner and must not fall back to the Writer as planner/research director.
- [x] Remove `search_findings` support and research-drafting rules from the Writer draft template; search data should only reach Writer through the Planner's document plan.
- [x] Stop passing raw passive reference attachments directly into the Writer draft template; let the Planner curate/summarize them first.
- [x] Fix DuckDuckGo result parsing to use the real result link element/redirect format, not the displayed URL element only.
- [x] Add tests using realistic DuckDuckGo HTML and crawled-page failure modes.
- [x] Fix query-list parsing edge cases in `_generate_search_queries` and add tests for numbered lists, bullet lists, and malformed model output.
- [x] Decide whether Researcher should summarize each source itself or whether Planner should synthesize from structured JSON; document the chosen boundary.
  - Decision: Researcher performs deterministic source extraction and compaction only; Planner performs the semantic synthesis and chooses what source notes/citation instructions reach the Writer.
  - Future option: add an explicit Researcher summarization sub-step only if deterministic snippets/excerpts are insufficient for quality.

---

## Smoke Scenario Gate

Status: `[x] Added`

Objective: Catch integration and role-boundary regressions that unit tests can miss, without requiring a full real-provider writing run.

Runner:

```powershell
poetry run python scripts/ocr_research_smoke_runner.py web_search_off_standard_pipeline
poetry run python scripts/ocr_research_smoke_runner.py web_search_on_researcher_boundary
poetry run python scripts/ocr_research_smoke_runner.py reference_attachment_planner_only
poetry run python scripts/ocr_research_smoke_runner.py uploaded_continuation_source
poetry run python scripts/ocr_research_smoke_runner.py mistral_ocr_direct
poetry run python scripts/ocr_research_smoke_runner.py real_llm_web_research
```

Scenarios:

- [x] `web_search_off_standard_pipeline`: verifies that disabling the activator keeps the standard pipeline and does not call Researcher.
- [x] `web_search_on_researcher_boundary`: verifies Planner + Researcher integration and proves raw search findings do not reach Writer.
- [x] `reference_attachment_planner_only`: verifies passive reference attachments reach Planner but not Writer as raw context.
- [x] `uploaded_continuation_source`: verifies uploaded Markdown can be split into continuation sections and terminal references are recognized.
- [x] `mistral_ocr_direct`: verifies the configured Mistral key can OCR a generated PDF and preserve a unique marker.
- [x] `real_llm_web_research`: verifies the current real Planner/Writer configuration can run with web search enabled while preserving the Planner/Researcher/Writer role boundary.

Latest local run:

- [x] 2026-06-16: all five scenarios passed locally. Notes are written to `dev_docs/OCR_RESEARCH_SMOKE_NOTES.md`; JSONL logs are written under `exports/_smoke_ocr_research/`.
- [x] 2026-06-16: `real_llm_web_research` passed locally with real `zen` Planner/Writer calls. Search findings were non-empty, Planner produced a source-aware plan, and Writer did not leak the raw reference marker.
