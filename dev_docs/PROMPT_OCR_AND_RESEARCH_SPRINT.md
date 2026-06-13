# Prompt Enhancement, Mistral OCR Attachments & Web Research Sprint

Date: 2026-06-13  
Status: In progress
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
