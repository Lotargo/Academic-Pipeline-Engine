from __future__ import annotations

import logging
from typing import Optional, Protocol

from academic_pe.manifests.resolver import ArtifactManifestResolver, ResolvedArtifactManifest

logger = logging.getLogger(__name__)


class PromptEnhancerManifestResolver(Protocol):
    def resolve(
        self,
        *,
        topic: str = "",
        instructions: str = "",
        academic_mode: bool = False,
        language: str = "auto",
        mode: str = "new",
        continuation_metadata: Optional[dict] = None,
    ) -> ResolvedArtifactManifest:
        ...


_ARTIFACT_GUIDANCE = {
    "creative_poem": (
        "Preserve the artifact as a poem. Improve the brief through line count, stanza shape, imagery, rhythm, "
        "speaker, mood, and requested constraints only."
    ),
    "creative_story": (
        "Preserve the artifact as narrative prose. Improve the brief through narrator, setting, conflict, pacing, "
        "tone, audience, and boundaries only."
    ),
    "school_essay": (
        "Preserve the school-level assignment. Improve clarity, thesis, age-appropriate structure, and natural "
        "student register without research overkill."
    ),
    "academic_paper": (
        "Preserve the academic artifact. Add methodological clarity, evidence discipline, terminology, and source "
        "expectations only where they fit the user's request."
    ),
    "technical_readme": (
        "Preserve the README artifact. Improve practical sections such as overview, installation, usage, "
        "configuration, limitations, and concrete examples without academic prose."
    ),
    "plan_document": (
        "Preserve the plan artifact. Improve goals, tasks, milestones, owners, risks, and acceptance criteria "
        "without turning it into an essay."
    ),
    "report": (
        "Preserve the report artifact. Improve summary, findings, implications, evidence needs, and scope without "
        "forcing research-paper apparatus."
    ),
    "continuation_source": (
        "Preserve the previous artifact's genre, structure, audience, and voice. Treat the new instruction as a "
        "continuation or revision unless it explicitly changes the artifact type."
    ),
    "unknown_freeform": (
        "Use preserve-first fallback behavior. Preserve the apparent artifact type and user structure, improve "
        "minimally, and do not invent academic sections or bureaucracy."
    ),
}


def build_prompt_enhancement_prompt(
    *,
    topic: str,
    instructions: Optional[str],
    language: str,
    academic_mode: bool = False,
    continuation_metadata: Optional[dict] = None,
    resolver: Optional[PromptEnhancerManifestResolver] = None,
) -> str:
    resolved = _resolve_manifest(
        topic=topic,
        instructions=instructions or "",
        language=language,
        academic_mode=academic_mode,
        continuation_metadata=continuation_metadata,
        resolver=resolver,
    )

    sections = [
        "You are a manifest-driven prompt enhancer for an automated document pipeline.",
        (
            "Your task is to refine the user's raw topic and instructions without changing the requested artifact "
            "type, genre, audience, voice, style, structure, or constraints."
        ),
        (
            f"Generate the enhanced topic and instructions in the language corresponding to '{language}' "
            "(e.g., if 'ru' write in Russian, if 'en' write in English)."
        ),
        "",
        f"Raw Topic: {topic}",
        f"Raw Guidelines/Instructions: {instructions or ''}",
        "",
        _contract_section(resolved),
        "",
        "PromptEnhancer adapter rules:",
        "1. Clarify the brief; reduce ambiguity; preserve the artifact type.",
        (
            "2. Do not add new scope, title pages, rubrics, citations, source requirements, headings, formulas, "
            "plots, tables, or bureaucracy unless the user explicitly asked for them or the contract requires them."
        ),
        (
            "3. Preserve all concrete details from the raw request: title, characters, setting, required phrases, "
            "class/year, author name, length, style, forbidden words, desired mood, and continuation constraints."
        ),
        (
            "4. For creative writing, improve only the creative brief: imagery, mood, voice, rhythm, rhyme, "
            "narrator, target audience, length, and boundaries."
        ),
        (
            "5. For school-level or informal tasks, keep the requested level and natural language. Do not make the "
            "output more academic, technical, formal, or adult than requested."
        ),
        (
            "6. Academic mode means compatible rigor, not automatic research-paper structure. Keep the artifact "
            "itself unless the user explicitly asks to change it."
        ),
        (
            "7. Keep the pipeline constraints digital: never add physical-world instructions such as printing, "
            "binding, physical submission, or hand-signing."
        ),
        (
            "8. Explicitly forbid placeholders, AI self-references, apology wrappers, and meta-text that would "
            "appear in the final generated document."
        ),
        "",
        "Internal candidate-and-critic process:",
        "- Draft a conservative enhancement that preserves the raw request.",
        "- Draft a more detailed enhancement only if it does not add new scope.",
        "- Draft a creative or structural enhancement only when compatible with the artifact contract.",
        (
            "- Reject any candidate that changes artifact type, loses user details, adds bureaucracy, introduces "
            "academic drift, or violates forbid clauses."
        ),
        "- Return only the best repaired candidate.",
        "",
        (
            "Return ONLY a valid JSON object matching the schema below. Do not include markdown code block fences, "
            "wrapper text, or explanations outside the JSON object."
        ),
        "Schema:",
        "{",
        '  "topic": "Enhanced topic/title that preserves the requested genre",',
        '  "instructions": "Concise, genre-preserving writing instructions for the pipeline"',
        "}",
    ]
    return "\n".join(sections)


def _resolve_manifest(
    *,
    topic: str,
    instructions: str,
    language: str,
    academic_mode: bool,
    continuation_metadata: Optional[dict],
    resolver: Optional[PromptEnhancerManifestResolver],
) -> Optional[ResolvedArtifactManifest]:
    selected_resolver = resolver or ArtifactManifestResolver()
    try:
        return selected_resolver.resolve(
            topic=topic,
            instructions=instructions,
            academic_mode=academic_mode,
            language=language,
            mode="continuation" if continuation_metadata else "new",
            continuation_metadata=continuation_metadata,
        )
    except Exception as exc:
        logger.warning("Prompt enhancer artifact manifest resolution skipped: %s", exc)
        return None


def _contract_section(resolved: Optional[ResolvedArtifactManifest]) -> str:
    if resolved is None:
        return (
            "[Active Artifact Contract]\n"
            "No manifest contract could be resolved. Use preserve-first fallback behavior: keep the apparent "
            "artifact type, improve minimally, and do not invent academic structure."
        )

    contract = resolved.contract
    evidence = resolved.evidence
    artifact_guidance = _ARTIFACT_GUIDANCE.get(
        contract.artifact,
        "Preserve the detected artifact and improve only what the user asked to improve.",
    )
    confidence_note = ""
    if evidence.confidence < 0.5:
        confidence_note = (
            "\nSelection confidence is low; treat the manifest as a fallback hint and preserve the user's apparent "
            "form instead of inventing structure."
        )

    return (
        "[Active Artifact Contract]\n"
        "Use this compact contract as the highest-priority artifact intent for prompt enhancement.\n"
        f"Detected artifact: {contract.artifact}\n"
        f"Selection confidence: {evidence.confidence:.2f}\n"
        f"Matched phrases: {', '.join(evidence.matched_phrases) if evidence.matched_phrases else 'none'}\n"
        f"Adapter guidance: {artifact_guidance}{confidence_note}\n"
        f"{resolved.contract_sexpr.strip()}"
    )
