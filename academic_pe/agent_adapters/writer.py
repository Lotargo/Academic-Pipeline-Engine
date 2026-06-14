from __future__ import annotations

from typing import Optional

_GENRE_GUIDANCE_WRITER = {
    "creative_poem": (
        "Lyrical/Poetic writing checks:\n"
        "- Focus on natural voice, rhythm, imagery, and emotional coherence.\n"
        "- Avoid clinical summary tones, forced structures, or explanations of the poem's meaning."
    ),
    "creative_story": (
        "Creative story writing checks:\n"
        "- Use a natural narrative voice, showing instead of telling, and focus on style, pacing, and character consistency.\n"
        "- Reject sterile summary tones, moralizing explanations, or machine-like transitions."
    ),
    "school_essay": (
        "School composition writing checks:\n"
        "- Maintain an age-appropriate, natural student register.\n"
        "- Avoid overly dense research paper structure or professional scientific vocabulary unless requested."
    ),
    "technical_readme": (
        "Technical README writing checks:\n"
        "- Write practical, concrete installation, usage, and configuration instructions.\n"
        "- Avoid inventing fictitious features, and keep the focus on clear developer instructions."
    ),
    "academic_paper": (
        "Academic writing checks:\n"
        "- Use formal, analytical, and conceptually precise language.\n"
        "- Reject generic AI filler phrases, disclaimers, or empty transitional sentences."
    ),
}


def contract_guidance(artifact_id: Optional[str] = None) -> str:
    base = (
        "Writer: produce final content that obeys the contract; do not output analysis of the contract. Preserve "
        "voice, genre, audience level, pacing, structure, mode clauses, and negative constraints."
    )
    genre = _GENRE_GUIDANCE_WRITER.get(artifact_id) if artifact_id else None
    if genre:
        return f"{base}\n{genre}"
    return base
