# Manifest And Contract Architecture

This document records the runtime boundaries for artifact-first generation.
The goal is to keep artifact routing, contract compilation, prompt rendering,
and validation testable without LLM calls.

## Data Flow

```text
user request / continuation metadata
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

## Package Ownership

`academic_pe.manifests`

- Loads YAML manifest data.
- Owns artifact selection, fallback policy, continuation inheritance, and
  selection evidence.
- Must not render LLM prompts.
- Must not call agents or providers.

`academic_pe.contracts`

- Owns `ArtifactContract` and `AgentContract` models.
- Compiles manifests into validated contracts.
- Renders deterministic S-expressions.
- Runs contract-vs-output drift checks independently from the Reviewer LLM.
- Must not load YAML files or call agents/providers.
- Must not evaluate contract data as code.

`academic_pe.agent_adapters`

- Converts artifact/agent intent into role-specific prompt guidance.
- May render prompt-enhancer prompts.
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
- Must not duplicate manifest selection heuristics, contract compilation rules,
  or adapter-specific prompt policy.

`academic_pe.server`

- Owns HTTP request/response handling and run-state persistence.
- May call orchestration and prompt-enhancement APIs.
- Must not contain manifest selection heuristics, contract compilation rules,
  drift logic, or adapter-specific policy.

`academic_pe.agents`

- Receive rendered contract instructions through their system prompts.
- May run the configured one-pass self-critique.
- Must not load manifests directly.
- Must not compile contracts.

## Configuration Boundary

`config/artifact_manifests.yaml` is data-only. It may contain:

- manifest `id` and `version`;
- artifact type;
- style, audience, and structure defaults;
- requirements and negative constraints;
- content-boundary overlays;
- execution-mode overlays.

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
