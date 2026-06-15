# Manifest And Contract Architecture

This document records the runtime boundaries for artifact-first generation.
The goal is to keep artifact routing, contract compilation, prompt rendering,
and validation testable without LLM calls.

Academic Pipeline Engine treats the requested output as an artifact first, not
as an academic paper by default. The manifest/contract layer determines what
kind of artifact the user asked for, compiles that intent into deterministic
runtime data, and then injects concise role-specific guidance into agents.

## Data Flow

```text
user request / API overrides / continuation metadata
  -> ArtifactManifestResolver
  -> ArtifactManifest + ManifestSelectionEvidence
  -> ArtifactContract
  -> contract S-expression + metadata
  -> PromptManifestResolver
  -> agent system prompts with artifact and agent contracts
  -> agents
  -> drift checks and reviewer gate
```

Prompt enhancement follows the same manifest resolver and contract compiler, but
it builds its prompt before the normal orchestrator path. It therefore renders
its own prompt-enhancer agent contract.

Continuation follows the same path with additional metadata. The resolver may
inherit the previous resolved manifest/contract, previous prompt, runtime
template, document plan, section order, and compact style samples. Current user
instructions still take priority over inherited metadata.

## Artifact-First Modes

The project uses two execution modes:

- `standard` preserves the requested artifact type and avoids unnecessary
  academic apparatus.
- `academic` adds rigor, evidence discipline, assumptions, and limitations where
  they fit the artifact.

Academic mode must not blindly force citations, charts, formulas, title pages,
or research-paper sections into poems, stories, school essays, README files, or
plans. Visualization and research-paper structure are contract properties, not
global side effects of a boolean flag.

## Package Ownership

`academic_pe.manifests`

- Loads YAML manifest data.
- Owns artifact selection, fallback policy, continuation inheritance, and
  selection evidence.
- Emits compact decision summaries suitable for metadata/debug display.
- Must not render LLM prompts.
- Must not call agents or providers.

`academic_pe.contracts`

- Owns `ArtifactContract` and `AgentContract` models.
- Compiles manifests into validated contracts.
- Renders deterministic S-expressions.
- Runs contract-vs-output drift checks independently from the Reviewer LLM.
- Owns hard-gate checks for obvious contract violations such as forbidden
  citations, title pages, rubrics, visualizations, genre drift, and AI markers.
- Must not load YAML files or call agents/providers.
- Must not evaluate contract data as code.

`academic_pe.agent_adapters`

- Converts artifact/agent intent into role-specific prompt guidance.
- May render prompt-enhancer prompts.
- Provides planner, writer, reviewer, researcher, exporter, and prompt-enhancer
  guidance from the same resolved artifact contract.
- Must not load manifest files directly.
- Must not perform artifact selection.

`academic_pe.core.prompt_manifest_resolver`

- Composes template prompt metadata, rendered artifact contracts, and rendered
  agent contracts into agent system prompts.
- Must stay deterministic and LLM-free.

`academic_pe.core.orchestrator`

- Coordinates template selection, artifact manifest resolution, agent creation,
  quality gates, drift checks, and rendering.
- May call the manifest resolver and contract drift API.
- Stores runtime template, runtime prompt manifest, resolved manifest, resolved
  contract, contract S-expression, selection evidence, and decision summary in
  run metadata.
- Must not duplicate manifest selection heuristics, contract compilation rules,
  or adapter-specific prompt policy.

`academic_pe.server`

- Owns HTTP request/response handling and run-state persistence.
- May call orchestration and prompt-enhancement APIs.
- May expose compact routing metadata to the UI and persist user
  `artifact_override`.
- Must not contain manifest selection heuristics, contract compilation rules,
  drift logic, or adapter-specific policy.

`academic_pe.agents`

- Receive rendered contract instructions through their system prompts.
- May run the configured one-pass self-critique.
- Must not load manifests directly.
- Must not compile contracts.

`academic_pe.tools`

- Renders and validates export artifacts.
- May use exporter-specific guidance that has already been compiled elsewhere.
- Must not select manifests, compile contracts, or reinterpret user intent.

## Configuration Boundary

`config/artifact_manifests.yaml` is data-only. It may contain:

- manifest `id` and `version`;
- artifact type;
- style, audience, and structure defaults;
- requirements and negative constraints;
- content-boundary overlays;
- execution-mode overlays;
- visualization policy and compatibility rules.

It must not contain executable code, Python snippets, dynamic imports, macros,
or eval-like directives.

## Contract DSL Rules

The contract DSL is a small S-expression rendering of validated Python data.
It is intentionally not EDN, Clojure, or a programmable language.

- No eval.
- No macros.
- No arbitrary code execution.
- Stable ordering for rendered mappings.
- String values are escaped before rendering.
- Validation happens in Python before prompts are assembled.

If the project later considers a real EDN/Clojure runtime, it needs a separate
ADR documenting the security, dependency, portability, and testability tradeoffs.

## Drift And Review

Contract drift checks are deterministic hard gates for obvious violations such
as AI markers, forbidden academic apparatus, forbidden visualizations, citation
drift, title-page drift, rubric drift, and genre/style drift.

The Reviewer LLM remains the external qualitative gate. Agents should already
self-correct before Reviewer sees the content, but Reviewer approval is still
independent from the internal self-critique pass.

## Metadata

Run and export metadata may store:

- `resolved_manifest`;
- `resolved_contract`;
- `contract_sexpr`;
- `manifest_selection`;
- `decision_summary`;
- `artifact_override`;
- runtime template and runtime prompt manifest snapshots.

Metadata should be compact and diagnostic. It may record selected manifest ids,
confidence, matched phrases, active mode, and short ambiguity notes. It must not
store long private reasoning transcripts.

## UI Visibility

The UI can show a compact routing summary such as:

```text
Detected: Technical README · Standard · No citations
```

Artifact override should remain available even when confidence is high, and
should be visually promoted when confidence is low. Overrides are persisted into
run/export metadata and passed back into manifest resolution.
