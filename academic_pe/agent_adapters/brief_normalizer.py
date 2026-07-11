from __future__ import annotations

from typing import Optional

from academic_pe.manifests.resolver import ArtifactManifestResolver


def build_brief_normalization_prompt(
    *,
    topic: str,
    instructions: Optional[str],
    language: str,
    academic_mode: bool = False,
    continuation_metadata: Optional[dict] = None,
    artifact_override: Optional[str] = None,
) -> str:
    """Build a bounded extraction task; it must not design downstream prompts."""
    artifact_hint = artifact_override
    if artifact_hint is None:
        try:
            resolved = ArtifactManifestResolver().resolve(
                topic=topic,
                instructions=instructions or "",
                execution_mode="academic" if academic_mode else "standard",
                language=language,
                mode="continuation" if continuation_metadata else "new",
                continuation_metadata=continuation_metadata,
            )
            artifact_hint = resolved.contract.artifact
        except Exception:
            artifact_hint = None
    return "\n".join([
        "You are BriefNormalizer. Extract user intent into typed data without expanding scope.",
        "Do not write a Writer prompt, propose a document outline, add research, or invent requirements.",
        f"Language policy: {language}",
        f"Raw topic: {topic}",
        f"Raw instructions: {instructions or ''}",
        f"Advisory artifact hint: {artifact_hint or 'unknown'}",
        "Preserve concrete user wording. Put genuine uncertainty in unresolved_ambiguities instead of guessing.",
        "Return exactly one JSON object with no Markdown fences and only these fields:",
        '{"topic":"non-empty topic","artifact_hints":[],"explicit_requirements":[],"explicit_forbids":[],',
        '"audience":null,"tone":null,"length_hint":null,"unresolved_ambiguities":[]}',
    ])
