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

## Architecture Decisions

These decisions resolve the initial open design questions and should guide implementation unless a later ADR explicitly changes them.

### Manifest Source And Runtime Boundary

Decision: Use YAML as the editable source of truth for manifests, with Python/Pydantic models as the runtime schema, validation, and compilation boundary.

Implications:
- Manifest files remain data-only and must not contain executable code.
- YAML manifests are loaded into Pydantic models before use.
- Contract compilation, validation, fallback behavior, and prompt rendering happen in Python.
- Future JSON import/export is acceptable, but runtime behavior still goes through the same models and validators.

### UI Artifact Override

Decision: Always show compact detection state, always make override available, and visually promote override only when confidence is low.

Target behavior:
- Normal display: `Detected: Poem · Standard · No citations`.
- If confidence is below the selected threshold, e.g. `< 0.65`, highlight that the user can correct the artifact type.
- The user can still open the detected artifact chip/dropdown and override even when confidence is high.

### Decision Summary Metadata

Decision: Store short factual audit metadata, not reasoning transcripts or chain-of-thought.

Allowed shape:

```json
{
  "selected_manifest": "creative_poem",
  "confidence": 0.85,
  "matched_phrases": ["poem", "12 lines"],
  "mode": "standard",
  "summary": "Detected poem request; preserving creative form and forbidding academic apparatus."
}
```

Rules:
- Keep summaries brief and diagnostic.
- Include selection facts, active mode, and one concise ambiguity note when useful.
- Do not store rejected candidate chains, private reasoning, or long internal critique text.

### Human-Style Checks

Decision: Use a hybrid guardrail system.

Policy:
- Rule-based checks act as hard gates for obvious markers: AI self-reference, placeholders, apology wrappers, template filler, title-page/rubric drift, forced citations, and forbidden academic apparatus.
- LLM reviewer checks act as soft qualitative review for genre fit, natural voice, audience appropriateness, mechanical structure, and stale or generic prose.
- "Human style" means natural prose appropriate to the requested artifact. It must not mean deception, provenance hiding, or attempts to bypass AI detectors.

### Adult Creative Boundaries

Decision: Represent adult/erotic material as a content-boundary overlay on top of the artifact type, not as a separate primary artifact identity.

Example:

```yaml
content_boundaries:
  adult_content:
    explicitness: user_requested
    require_all_characters_adult: true
    require_consent: true
    forbid: [minors, coercion, non_consensual, incest, sexual_violence]
```

Implications:
- A requested adult story remains a `creative_story` with additional content boundaries.
- Story structure, voice, pacing, and genre preservation still come from the artifact manifest.
- Safety/content policy is composed as an overlay and must not force academicization, rubric text, or moralizing wrappers.

## Status Legend

- `[x] Completed`
- `[~] In progress`
- `[ ] Planned / Pending`
- `[!] Needs design decision`

---

## Workstream 1: Manifest Architecture

Status: `[~] In progress`

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

Status: `[~] In progress`

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

Status: `[~] In progress`

Objective: Give each agent a manifest adapter so the same artifact manifest is interpreted correctly for that agent's job.

Tasks:
- [x] Add prompt-enhancer adapter:
  - clarify the brief;
  - preserve artifact type;
  - do not add new scope or bureaucracy.
- [x] Add planner adapter:
  - choose artifact-compatible structure;
  - avoid academic sections unless the artifact is academic;
  - preserve continuation structure when present.
- [x] Add writer adapter:
  - write final content, not instructions;
  - preserve voice, genre, audience level, and pacing;
  - respect negative constraints.
- [x] Add reviewer adapter:
  - detect genre drift, style drift, audience drift, structure drift, and prompt loss;
  - reject incompatible academicization or bureaucracy;
  - check missing user constraints.
- [x] Add researcher adapter:
  - run only when the artifact needs current facts/sources or the user enabled search;
  - avoid forcing citations into creative or purely personal artifacts unless requested.
- [x] Add exporter adapter:
  - apply formatting appropriate to artifact type;
  - avoid title pages, headings, or citation sections unless requested or manifest-required.

---

## Workstream 4: Standard vs Academic Execution Modes

Status: `[x] Complete`

Objective: Make `academic_mode` a manifest overlay that changes reasoning depth and quality discipline without destroying the requested artifact type.

Rationale:
- The current academic mode is too easy to interpret as "add charts/tables/formulas everywhere".
- Academic mode should mean disciplined thinking, source awareness, critical analysis, methodological clarity, and stronger self-checking.
- A poem, story, README, plan document, essay, or adult creative artifact can have an academic-mode treatment, but it should not automatically become a generic research paper.

Mode rules:
- [x] Standard mode preserves the requested artifact and avoids unnecessary formal apparatus.
- [x] Academic mode adds rigor only where compatible with the artifact.
- [x] Academic mode may require evidence, definitions, method notes, conceptual framing, or source discipline for analytical artifacts.
- [x] Academic mode may request charts/tables/formulas only when they naturally support the artifact and user task.
- [x] Academic mode must not force visualization into creative writing, poetry, personal narratives, or README-style documentation unless explicitly requested.
- [x] Academic mode must not override adult/creative/school/technical genre constraints; it should apply a more thoughtful version of that genre.

Examples:
- Poem + standard mode: lyrical brief, rhythm, imagery, human voice.
- Poem + academic mode: can become a literary-style poetic artifact with stronger control of motif, symbolism, form, and intertextual awareness, but still a poem unless the user asks for analysis.
- Story + academic mode: can improve narrative structure, theme, conflict, psychological coherence, and literary craft, but should not become a rubric or research article.
- README + academic mode: can improve technical precision, reproducibility, architecture clarity, and limitations, but should not add citations by default.
- Academic paper + academic mode: may use methodology, citations, formulas, tables, and evidence discipline when relevant.

Tasks:
- [x] Represent execution mode as a manifest overlay, not as scattered boolean checks. Manifest `modes.*` overlays compile into `ArtifactContract.execution_mode`; `academic_mode` remains only as a UI/API/config compatibility input.
- [x] Add `standard_mode` and `academic_mode` contract clauses.
- [x] Remove hard-coded "must include plot/chart" logic from generic academic-mode prompts.
- [x] Move visualization requirements into artifact-compatible manifest rules.
- [x] Add tests proving academic mode does not force charts/tables/formulas into incompatible artifact types.
- [x] Add tests proving academic paper + academic mode still receives proper scientific rigor.

Implementation notes:
- Generic draft/plan/revision/review prompts no longer default to `academic document`, `academic tone`, or `material academic quality`.
- Agent config prompts and dynamic example defaults are now artifact-aware instead of academic-paper-first.
- Default manifest tests cover poem/readme boundaries and academic-paper rigor/visualization behavior.
- Contracts now carry `clauses` such as `standard_mode` and `academic_mode`; S-expression contract blocks render them for all agent adapters.
- Orchestrator runtime prompt flags are derived from the resolved contract first, with legacy pipeline flags only as fallback for direct/non-manifest calls.
- Prompt enhancement accepts the same compatibility mode input and converts it into execution-mode clauses before rendering the active artifact contract.

---

## Workstream 5: Independent Self-Critique Phase

Status: `[~] In progress`

Objective: Add a non-blocking critical-analysis phase inside agents so they improve their own output before handing it forward.

Rationale:
- Prompt-level criticism can catch conceptual drift, weak structure, missing constraints, and style mismatch more reliably.
- This critic must not become another Reviewer that blocks the pipeline. It should rewrite/improve the agent's own output directly.

Pattern:

```text
agent draft
→ independent critic pass
→ self-repair/rewrite
→ final agent output
```

Agent-specific behavior:
- [x] PromptEnhancer critic checks whether enhancement changed artifact type, added bureaucracy, or lost user details; then rewrites the enhanced prompt itself.
- [x] Planner critic checks whether the plan follows the manifest, preserves genre/style, avoids academic drift, and handles continuation; then rewrites the plan itself.
- [x] Writer critic checks whether the draft obeys the contract, avoids AI markers, preserves voice, and satisfies user constraints; then rewrites the content itself.
- [ ] Researcher critic checks source relevance, citation quality, and overreach; then rewrites findings itself.
- [ ] Exporter/renderer critic checks structure/format compatibility where possible.

Constraints:
- [x] Self-critique must not ask the user for approval.
- [x] Self-critique must not return a rejection state.
- [x] Self-critique must not create an infinite revision loop.
- [x] Self-critique output should be concise internally and should not leak long chain-of-thought.
- [x] Store only a short `self_critique_summary` in debug metadata when needed.
- [ ] Reviewer remains the external quality gate, but agents should already have self-corrected before Reviewer sees the content.

Academic-mode additions:
- [~] In academic mode, self-critique should include stronger critical thinking:
  - weak assumptions;
  - unsupported claims;
  - conceptual contradictions;
  - shallow definitions;
  - missing limitations;
  - source/evidence gaps when sources are required.
- [~] The self-critic repairs these issues directly instead of sending the document back as a blocker.

Implementation notes:
- `AgentConfig.self_critique.enabled` controls the extra one-pass LLM call; default is disabled to avoid surprise cost changes.
- Self-critique returns compact JSON with `summary` and repaired `output`; invalid JSON, empty repairs, or blocking feedback fall back to the original draft.
- Writer and Planner store only `last_self_critique_summary`; Orchestrator collects short summaries into saved run metadata.

---

## Workstream 6: Artifact Contract DSL / S-Expression Layer

Status: `[~] In progress`

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
- [x] Define an internal `ArtifactContract` Python model.
- [x] Support JSON/YAML serialization for metadata.
- [x] Add a deterministic S-expression renderer for prompt injection.
- [~] Add parser/validator tests for:
  - nested contract data;
  - string escaping;
  - stable ordering;
  - forbidden constraint names;
  - unknown artifact fallback.
- [x] Compile artifact manifests and agent adapters into agent-specific contracts:
  - prompt enhancer contract;
  - planner contract;
  - writer contract;
  - reviewer contract;
  - researcher contract;
  - exporter contract.
- [x] Persist the resolved contract in history metadata.
- [x] On continuation, inherit the previous resolved contract before applying the new user instruction.
- [x] Add drift checks that compare final agent output against the contract.

Design constraints:
- [x] The DSL must stay small and boring: no arbitrary code execution, no macros, no eval.
- [x] Contracts should be data, not programs.
- [x] LLMs may receive rendered S-expressions, but validation must happen in Python.
- [ ] If a real Clojure/EDN runtime is considered later, document the tradeoff first.

Implementation notes:
- Added `AgentContract` as a deterministic, validated adapter-specific wrapper around `ArtifactContract`.
- Added compiler policies for prompt enhancer, planner, writer, reviewer, researcher, exporter, renderer, and unknown-agent fallback behavior.
- Runtime prompts now include both `[Active Artifact Contract]` and `[Active Agent Contract]` when full resolved contract metadata is available.
- Prompt enhancement includes its own prompt-enhancer agent contract because it resolves manifests before the normal runtime prompt resolver path.

---

## Workstream 7: Prompt Enhancer Refactor

Status: `[~] In progress`

Objective: Replace the current single prompt-enhancement prompt with manifest-driven intent routing and controlled enhancement.

Tasks:
- [x] Add intent router for artifact type detection.
- [ ] Treat examples as illustrative, not exhaustive.
- [x] Add fallback behavior for unknown artifact types:
  - preserve apparent artifact type;
  - improve minimally;
  - do not convert to academic paper;
  - do not invent structure.
- [~] Add lightweight ToT-style candidate generation internally:
  - conservative candidate;
  - detailed candidate;
  - creative/structural candidate when appropriate.
- [x] Add critic/gate that rejects candidates that:
  - change artifact type;
  - add title pages/rubrics/citations without request;
  - introduce academic drift;
  - lose user details;
  - add AI markers or meta-text.
- [x] Return only the final `topic` and `instructions` JSON to the UI.
- [x] Optionally store a short `decision_summary` for debug metadata, without exposing long chain-of-thought.

---

## Workstream 8: Continuation Manifest Memory

Status: `[x] Complete`

Objective: Make continuation inherit the previous artifact's resolved behavior, not just previous text.

Tasks:
- [x] Save `resolved_manifest` into history metadata for every generation.
- [x] Save manifest selection evidence:
  - detected artifact type;
  - confidence;
  - user phrases that triggered selection;
  - ambiguity notes.
- [x] Continuation priority order:
  1. explicit current user instruction;
  2. previous resolved manifest;
  3. previous user prompt;
  4. previous document plan;
  5. previous document text/style;
  6. artifact manifest defaults;
  7. unknown fallback manifest.
- [x] If old history metadata lacks `resolved_manifest`, infer from stored prompt, plan, runtime template, and document text.
- [x] If inference confidence is low, preserve style from the existing text and avoid adding new structure.

Implementation notes:
- Low-confidence continuation now compiles explicit contract requirements to preserve source voice and avoid new sections unless requested.
- Resolver extracts compact source section order and source style samples from previous context/runtime metadata.
- These preservation hints are persisted in `resolved_contract`, rendered in the contract S-expression, and carried through orchestrator metadata.

---

## Workstream 9: AI-Marker And Human-Style Guardrails

Status: `[x] Complete`

Objective: Ensure all agents avoid obvious AI-generated markers and machine-like artifacts while preserving the requested genre.

Tasks:
- [x] Add global negative constraints for final content:
  - no AI self-reference;
  - no "as an AI" phrasing;
  - no meta-comments about generation;
  - no placeholders such as `[insert link]`;
  - no template filler;
  - no apology/explanation wrappers;
  - no evaluation rubric unless requested;
  - no mechanical over-structuring.
- [x] Add genre-specific human-style checks:
  - creative writing: natural voice, non-mechanical imagery, no sterile summary tone;
  - school writing: age-appropriate, natural student-like register when requested;
  - README: practical, concrete, no invented features;
  - academic writing: formal but not empty, no generic AI-style filler.
- [x] Add reviewer drift checks for:
  - artificial smoothness;
  - repeated syntactic patterns;
  - generic transitions;
  - meaningless balance phrases;
  - disclaimers or meta-text.
- [x] Ensure "human style" does not mean hiding provenance through deception; it means producing natural prose appropriate to the requested artifact without obvious machine artifacts.

Implementation notes:
- Contract drift checks now include deterministic genre/style markers keyed by artifact type.
- Creative poem/story checks reject obvious explanatory wrappers and sterile summary prose.
- School essay checks reject professional research-paper register when the artifact is school-level.
- README checks reject academic-paper prose in practical technical documentation.
- Academic paper checks reject generic filler phrases while leaving formal analytical prose intact.
- Writer and Reviewer adapter guidance explicitly define natural human style as artifact-appropriate prose, not false claims about authorship, provenance, or process.

---

## Workstream 10: UI And Debug Visibility

Status: `[~] In progress`

Objective: Make artifact routing visible enough to prevent surprises without overwhelming the user.

Tasks:
- [x] Show compact detected mode in the UI, e.g. `Detected: Poem · Creative mode · No citations`.
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
- [x] Add contract DSL tests proving agent prompts receive compact, stable, non-executable S-expression contracts.
- [ ] Add standard-vs-academic mode tests for creative, technical, README, and academic artifacts.
- [x] Add self-critique tests proving agents repair their own draft instead of returning a blocker.

---

## Resolved Design Questions

- [x] Artifact manifests are YAML source data plus Python/Pydantic runtime models and validators.
- [x] UI should always show detection and keep override available, with stronger prompting only on low confidence.
- [x] `decision_summary` should be a short factual audit record, not chain-of-thought.
- [x] Human-style checks should be hybrid: rule-based hard gates plus LLM qualitative review.
- [x] Adult/erotic creative boundaries should be content-boundary overlays, not separate primary artifact identities.
