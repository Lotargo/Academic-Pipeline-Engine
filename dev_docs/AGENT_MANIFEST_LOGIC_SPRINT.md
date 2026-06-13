# Agent Manifest Logic Sprint

Date: 2026-06-13  
Status: Planned  
Scope: Manifest-driven agent behavior, artifact-first routing, genre/style preservation, continuation memory, and AI-marker avoidance.

## Sprint Goal

Move the pipeline from an academic-first default to an artifact-first agent architecture.

Agents must first understand what kind of artifact the user wants, then adapt planning, writing, reviewing, enhancement, research, and export behavior to that artifact. Unknown or niche artifact types must not fall back to academic paper structure by default.

## Core Principle

Enhancement and generation must reduce ambiguity, not increase scope.

The system must preserve the user's requested artifact type, genre, voice, audience level, style, structure, and constraints unless the current user request explicitly asks to change them.

The pipeline has two execution modes:

- **Standard mode**: preserve the requested artifact type and produce a good natural result without unnecessary academic apparatus.
- **Academic mode**: apply scientific/critical thinking, stronger argumentation, evidence discipline, conceptual rigor, and structured analysis appropriate to the artifact. Academic mode must not blindly force plots, tables, formulas, citations, or research-paper structure into every artifact. It should adapt the artifact into an academically rigorous version of itself when appropriate.

## Status Legend

- `[x] Completed`
- `[~] In progress`
- `[ ] Planned / Pending`
- `[!] Needs design decision`

---

## Workstream 1: Manifest Architecture

Status: `[ ] Planned`

Objective: Introduce layered manifests that define document/artifact intent separately from agent execution behavior.

Tasks:
- [ ] Add `config/artifact_manifests.yaml`.
- [ ] Define artifact manifests for common types:
  - creative poem;
  - creative story / fairy tale;
  - school essay / composition;
  - academic paper;
  - technical README;
  - plan document;
  - report;
  - continuation source;
  - unknown / freeform fallback.
- [ ] Add manifest versioning (`id`, `version`) so old history items can keep stable behavior.
- [ ] Support manifest composition instead of one giant template per case:
  - artifact type;
  - style;
  - audience;
  - structure;
  - mode (`new`, `continuation`, `revision`);
  - safety/content boundaries where relevant;
  - negative constraints.
- [ ] Add `ArtifactManifestResolver` that selects and composes a runtime manifest from the user request and optional continuation metadata.
- [ ] Store the resolved runtime manifest in generation metadata.

---

## Workstream 2: Package Boundaries And Directory Layout

Status: `[ ] Planned`

Objective: Keep the manifest/contract system debuggable by separating responsibilities into explicit packages and directories instead of adding more logic to large monolithic modules.

Rationale:
- Manifest-driven orchestration will add resolvers, selectors, schemas, adapters, renderers, validators, and tests.
- If these are folded into `server.py`, generic `core` modules, or agent implementations directly, debugging will become slow and fragile.
- Each layer must have a clear ownership boundary and a small public API.

Proposed package layout:

```text
academic_pe/
  manifests/
    __init__.py
    models.py              # Pydantic models for artifact/style/adapter manifests
    loader.py              # YAML/JSON loading and version checks
    resolver.py            # Manifest selection and composition
    fallback.py            # Unknown-artifact fallback policy
    evidence.py            # Selection evidence and confidence records

  contracts/
    __init__.py
    models.py              # ArtifactContract and AgentContract models
    compiler.py            # Manifests -> resolved runtime contracts
    sexpr.py               # Deterministic S-expression renderer
    validator.py           # Rule/constraint validation, no eval
    drift.py               # Contract-vs-output drift checks

  agent_adapters/
    __init__.py
    prompt_enhancer.py     # Contract -> enhancer instructions
    planner.py             # Contract -> planner instructions
    writer.py              # Contract -> writer instructions
    reviewer.py            # Contract -> reviewer rubric/checks
    researcher.py          # Contract -> research/search policy
    exporter.py            # Contract -> export/formatting policy
```

Configuration layout:

```text
config/
  artifact_manifests.yaml
  style_manifests.yaml
  agent_adapter_manifests.yaml
  fallback_manifests.yaml
```

Test layout:

```text
tests/
  manifests/
    test_manifest_loader.py
    test_manifest_resolver.py
    test_fallback_policy.py

  contracts/
    test_contract_compiler.py
    test_sexpr_renderer.py
    test_contract_validator.py
    test_drift_checks.py

  agent_adapters/
    test_prompt_enhancer_adapter.py
    test_planner_adapter.py
    test_writer_adapter.py
    test_reviewer_adapter.py
```

Boundary rules:
- [ ] `server.py` may call the orchestration API but must not contain manifest selection, contract compilation, or adapter logic.
- [ ] Agents may receive rendered contract instructions but must not load manifests directly.
- [ ] Manifest loading must be isolated from prompt rendering.
- [ ] Contract rendering must be deterministic and testable without LLM calls.
- [ ] Drift checks must be callable independently from the Reviewer LLM.
- [ ] Config files must remain data-only; no embedded executable code.
- [ ] Each package must expose a small public API and keep implementation helpers private.
- [ ] Add architecture docs before broad integration so future changes know where new logic belongs.

---

## Workstream 3: Agent Adapter Manifests

Status: `[ ] Planned`

Objective: Give each agent a manifest adapter so the same artifact manifest is interpreted correctly for that agent's job.

Tasks:
- [ ] Add prompt-enhancer adapter:
  - clarify the brief;
  - preserve artifact type;
  - do not add new scope or bureaucracy.
- [ ] Add planner adapter:
  - choose artifact-compatible structure;
  - avoid academic sections unless the artifact is academic;
  - preserve continuation structure when present.
- [ ] Add writer adapter:
  - write final content, not instructions;
  - preserve voice, genre, audience level, and pacing;
  - respect negative constraints.
- [ ] Add reviewer adapter:
  - detect genre drift, style drift, audience drift, structure drift, and prompt loss;
  - reject incompatible academicization or bureaucracy;
  - check missing user constraints.
- [ ] Add researcher adapter:
  - run only when the artifact needs current facts/sources or the user enabled search;
  - avoid forcing citations into creative or purely personal artifacts unless requested.
- [ ] Add exporter adapter:
  - apply formatting appropriate to artifact type;
  - avoid title pages, headings, or citation sections unless requested or manifest-required.

---

## Workstream 4: Standard vs Academic Execution Modes

Status: `[ ] Planned`

Objective: Make `academic_mode` a manifest overlay that changes reasoning depth and quality discipline without destroying the requested artifact type.

Rationale:
- The current academic mode is too easy to interpret as "add charts/tables/formulas everywhere".
- Academic mode should mean disciplined thinking, source awareness, critical analysis, methodological clarity, and stronger self-checking.
- A poem, story, README, plan document, essay, or adult creative artifact can have an academic-mode treatment, but it should not automatically become a generic research paper.

Mode rules:
- [ ] Standard mode preserves the requested artifact and avoids unnecessary formal apparatus.
- [ ] Academic mode adds rigor only where compatible with the artifact.
- [ ] Academic mode may require evidence, definitions, method notes, conceptual framing, or source discipline for analytical artifacts.
- [ ] Academic mode may request charts/tables/formulas only when they naturally support the artifact and user task.
- [ ] Academic mode must not force visualization into creative writing, poetry, personal narratives, or README-style documentation unless explicitly requested.
- [ ] Academic mode must not override adult/creative/school/technical genre constraints; it should apply a more thoughtful version of that genre.

Examples:
- Poem + standard mode: lyrical brief, rhythm, imagery, human voice.
- Poem + academic mode: can become a literary-style poetic artifact with stronger control of motif, symbolism, form, and intertextual awareness, but still a poem unless the user asks for analysis.
- Story + academic mode: can improve narrative structure, theme, conflict, psychological coherence, and literary craft, but should not become a rubric or research article.
- README + academic mode: can improve technical precision, reproducibility, architecture clarity, and limitations, but should not add citations by default.
- Academic paper + academic mode: may use methodology, citations, formulas, tables, and evidence discipline when relevant.

Tasks:
- [ ] Represent execution mode as a manifest overlay, not as scattered boolean checks.
- [ ] Add `standard_mode` and `academic_mode` contract clauses.
- [ ] Remove hard-coded "must include plot/chart" logic from generic academic-mode prompts.
- [ ] Move visualization requirements into artifact-compatible manifest rules.
- [ ] Add tests proving academic mode does not force charts/tables/formulas into incompatible artifact types.
- [ ] Add tests proving academic paper + academic mode still receives proper scientific rigor.

---

## Workstream 5: Independent Self-Critique Phase

Status: `[ ] Planned`

Objective: Add a non-blocking critical-analysis phase inside agents so they improve their own output before handing it forward.

Rationale:
- LLMs often stay infected by the first reasoning path when critique is merely appended as the next instruction.
- A separate critic pass can catch conceptual drift, weak structure, missing constraints, and style mismatch more reliably.
- This critic must not become another Reviewer that blocks the pipeline. It should rewrite/improve the agent's own output directly.

Pattern:

```text
agent draft
→ independent critic pass
→ self-repair/rewrite
→ final agent output
```

Agent-specific behavior:
- [ ] PromptEnhancer critic checks whether enhancement changed artifact type, added bureaucracy, or lost user details; then rewrites the enhanced prompt itself.
- [ ] Planner critic checks whether the plan follows the manifest, preserves genre/style, avoids academic drift, and handles continuation; then rewrites the plan itself.
- [ ] Writer critic checks whether the draft obeys the contract, avoids AI markers, preserves voice, and satisfies user constraints; then rewrites the content itself.
- [ ] Researcher critic checks source relevance, citation quality, and overreach; then rewrites findings itself.
- [ ] Exporter/renderer critic checks structure/format compatibility where possible.

Constraints:
- [ ] Self-critique must not ask the user for approval.
- [ ] Self-critique must not return a rejection state.
- [ ] Self-critique must not create an infinite revision loop.
- [ ] Self-critique output should be concise internally and should not leak long chain-of-thought.
- [ ] Store only a short `self_critique_summary` in debug metadata when needed.
- [ ] Reviewer remains the external quality gate, but agents should already have self-corrected before Reviewer sees the content.

Academic-mode additions:
- [ ] In academic mode, self-critique should include stronger critical thinking:
  - weak assumptions;
  - unsupported claims;
  - conceptual contradictions;
  - shallow definitions;
  - missing limitations;
  - source/evidence gaps when sources are required.
- [ ] The self-critic repairs these issues directly instead of sending the document back as a blocker.

---

## Workstream 6: Artifact Contract DSL / S-Expression Layer

Status: `[ ] Planned`

Objective: Reduce LLM cognitive load and hallucination risk by compiling user intent and manifests into a compact, explicit, Lisp-like runtime contract.

Rationale:
- Agents should interpret and execute a resolved contract, not rediscover all rules from prose on every step.
- A small declarative contract makes intent easier to test, serialize, diff, store in metadata, and pass through continuation.
- The project should not require a Clojure/JVM runtime for the first implementation. Use a Clojure/Lisp-inspired representation while keeping the implementation in Python unless a later design decision justifies adding a JVM dependency.

Example rendered contract:

```clojure
(document
  (artifact creative_poem)
  (language ru)
  (style lyrical human natural)
  (audience general)
  (mode new)
  (forbid academic_drift title_page citations rubric ai_markers)
  (requirement theme "дама в красном")
  (requirement min_lines 12))
```

Tasks:
- [ ] Define an internal `ArtifactContract` Python model.
- [ ] Support JSON/YAML serialization for metadata.
- [ ] Add a deterministic S-expression renderer for prompt injection.
- [ ] Add parser/validator tests for:
  - nested contract data;
  - string escaping;
  - stable ordering;
  - forbidden constraint names;
  - unknown artifact fallback.
- [ ] Compile artifact manifests and agent adapters into agent-specific contracts:
  - prompt enhancer contract;
  - planner contract;
  - writer contract;
  - reviewer contract;
  - researcher contract;
  - exporter contract.
- [ ] Persist the resolved contract in history metadata.
- [ ] On continuation, inherit the previous resolved contract before applying the new user instruction.
- [ ] Add drift checks that compare final agent output against the contract.

Design constraints:
- [ ] The DSL must stay small and boring: no arbitrary code execution, no macros, no eval.
- [ ] Contracts should be data, not programs.
- [ ] LLMs may receive rendered S-expressions, but validation must happen in Python.
- [ ] If a real Clojure/EDN runtime is considered later, document the tradeoff first.

---

## Workstream 7: Prompt Enhancer Refactor

Status: `[ ] Planned`

Objective: Replace the current single prompt-enhancement prompt with manifest-driven intent routing and controlled enhancement.

Tasks:
- [ ] Add intent router for artifact type detection.
- [ ] Treat examples as illustrative, not exhaustive.
- [ ] Add fallback behavior for unknown artifact types:
  - preserve apparent artifact type;
  - improve minimally;
  - do not convert to academic paper;
  - do not invent structure.
- [ ] Add lightweight ToT-style candidate generation internally:
  - conservative candidate;
  - detailed candidate;
  - creative/structural candidate when appropriate.
- [ ] Add critic/gate that rejects candidates that:
  - change artifact type;
  - add title pages/rubrics/citations without request;
  - introduce academic drift;
  - lose user details;
  - add AI markers or meta-text.
- [ ] Return only the final `topic` and `instructions` JSON to the UI.
- [ ] Optionally store a short `decision_summary` for debug metadata, without exposing long chain-of-thought.

---

## Workstream 8: Continuation Manifest Memory

Status: `[ ] Planned`

Objective: Make continuation inherit the previous artifact's resolved behavior, not just previous text.

Tasks:
- [ ] Save `resolved_manifest` into history metadata for every generation.
- [ ] Save manifest selection evidence:
  - detected artifact type;
  - confidence;
  - user phrases that triggered selection;
  - ambiguity notes.
- [ ] Continuation priority order:
  1. explicit current user instruction;
  2. previous resolved manifest;
  3. previous user prompt;
  4. previous document plan;
  5. previous document text/style;
  6. artifact manifest defaults;
  7. unknown fallback manifest.
- [ ] If old history metadata lacks `resolved_manifest`, infer from stored prompt, plan, runtime template, and document text.
- [ ] If inference confidence is low, preserve style from the existing text and avoid adding new structure.

---

## Workstream 9: AI-Marker And Human-Style Guardrails

Status: `[ ] Planned`

Objective: Ensure all agents avoid obvious AI-generated markers and machine-like artifacts while preserving the requested genre.

Tasks:
- [ ] Add global negative constraints for final content:
  - no AI self-reference;
  - no "as an AI" phrasing;
  - no meta-comments about generation;
  - no placeholders such as `[insert link]`;
  - no template filler;
  - no apology/explanation wrappers;
  - no evaluation rubric unless requested;
  - no mechanical over-structuring.
- [ ] Add genre-specific human-style checks:
  - creative writing: natural voice, non-mechanical imagery, no sterile summary tone;
  - school writing: age-appropriate, natural student-like register when requested;
  - README: practical, concrete, no invented features;
  - academic writing: formal but not empty, no generic AI-style filler.
- [ ] Add reviewer drift checks for:
  - artificial smoothness;
  - repeated syntactic patterns;
  - generic transitions;
  - meaningless balance phrases;
  - disclaimers or meta-text.
- [ ] Ensure "human style" does not mean hiding provenance through deception; it means producing natural prose appropriate to the requested artifact without obvious machine artifacts.

---

## Workstream 10: UI And Debug Visibility

Status: `[ ] Planned`

Objective: Make artifact routing visible enough to prevent surprises without overwhelming the user.

Tasks:
- [ ] Show compact detected mode in the UI, e.g. `Detected: Poem · Creative mode · No citations`.
- [ ] Allow user override of artifact type when confidence is low or the detection is wrong.
- [ ] Add debug metadata view for:
  - manifest id/version;
  - confidence;
  - selection evidence;
  - active negative constraints.
- [ ] Persist user override into run metadata.

---

## Workstream 11: Tests

Status: `[ ] Planned`

Objective: Prevent regressions where unknown or creative requests are converted into academic tasks.

Tasks:
- [ ] Add golden tests for prompt enhancement:
  - poem -> no title page, no rubric, no citations by default;
  - children's story -> preserve childlike narrative voice;
  - erotic/adult story -> preserve narrative artifact type and requested boundaries;
  - school essay -> school-level structure, no research overkill;
  - README -> install/usage/config structure, no academic prose;
  - plan document -> deliverables/tasks, not essay;
  - unknown artifact -> minimal preserve-first enhancement;
  - academic paper -> academic apparatus allowed.
- [ ] Add planner tests proving selected sections match artifact type.
- [ ] Add writer tests proving output instructions preserve style/genre.
- [ ] Add reviewer tests for genre drift, academicization drift, rubric drift, and AI-marker detection.
- [ ] Add continuation tests proving previous resolved manifest is inherited.
- [ ] Add contract DSL tests proving agent prompts receive compact, stable, non-executable S-expression contracts.
- [ ] Add standard-vs-academic mode tests for creative, technical, README, and academic artifacts.
- [ ] Add self-critique tests proving agents repair their own draft instead of returning a blocker.

---

## Open Design Questions

- [!] Should artifact manifests be YAML-only, Python models, or both?
- [!] Should UI expose artifact override always, or only when confidence is below a threshold?
- [!] How detailed should `decision_summary` be without leaking chain-of-thought?
- [!] Should "human-style" checks be rule-based, LLM-reviewed, or hybrid?
- [!] How should adult/erotic creative writing boundaries be represented in manifests without overfitting?
