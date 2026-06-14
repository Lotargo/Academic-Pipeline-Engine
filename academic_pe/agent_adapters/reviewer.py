from __future__ import annotations

from typing import Optional

_GENRE_GUIDANCE_REVIEWER = {
    "creative_poem": (
        "Poetic Reviewer checks:\n"
        "- Verify that the output is purely creative text without explanations, metadata, or AI wrappers.\n"
        "- Reject any clinical summary tone or forced stanzas."
    ),
    "creative_story": (
        "Story Reviewer checks:\n"
        "- Ensure the narrative flow is natural and preserves genre/voice.\n"
        "- Reject sterile summaries, template transitions, or moralizing wrap-ups."
    ),
    "school_essay": (
        "School Essay Reviewer checks:\n"
        "- Verify that the essay is student-appropriate and does not look like a professional research publication.\n"
        "- Ensure the student register is natural and consistent."
    ),
    "technical_readme": (
        "Technical README Reviewer checks:\n"
        "- Verify that all instructions (install, run, config) are realistic and developer-friendly.\n"
        "- Reject mock placeholders, fabricated functionality, or generic text."
    ),
    "academic_paper": (
        "Academic Reviewer checks:\n"
        "- Verify logical argumentation, conceptual rigor, and evidence discipline.\n"
        "- Reject any generic AI filler phrases, empty transitions, or meta-comments."
    ),
}


def contract_guidance(artifact_id: Optional[str] = None) -> str:
    base = (
        "Reviewer: check for genre, style, audience, structure, prompt, and forbidden-clause drift against the "
        "contract. Treat standard_mode and academic_mode clauses as binding. Reject incompatible academicization, "
        "bureaucracy, missing user constraints, and AI/meta markers. Look for and reject artificial smoothness, "
        "repeated syntactic patterns, generic transitions, meaningless balance phrases, disclaimers, or meta-text."
    )
    genre = _GENRE_GUIDANCE_REVIEWER.get(artifact_id) if artifact_id else None
    if genre:
        return f"{base}\n{genre}"
    return base
