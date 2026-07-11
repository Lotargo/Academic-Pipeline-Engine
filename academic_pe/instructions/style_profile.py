from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field


class StyleProfile(BaseModel):
    """Observable style traits extracted only from text supplied by the user."""

    model_config = ConfigDict(extra="forbid")

    sample_origin: str = "user_sample"
    language: str = "unknown"
    formality: str = "neutral"
    terminology_density: float = Field(default=0.0, ge=0.0, le=1.0)
    paragraph_words: int = Field(default=0, ge=0)
    heading_preference: str = "none"
    list_preference: str = "none"
    first_person_allowed: bool = False
    transition_style: str = "implicit"
    preserve_only_observed_traits: bool = True


def extract_style_profile(sample: str, *, origin: str = "user_sample") -> StyleProfile | None:
    text = (sample or "").strip()
    words = re.findall(r"[A-Za-zА-Яа-яЁё][\w-]*", text, flags=re.UNICODE)
    if len(words) < 20:
        return None
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    average = round(len(words) / max(1, len(paragraphs)))
    cyrillic = len(re.findall(r"[А-Яа-яЁё]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    language = "ru" if cyrillic > latin else "en" if latin else "unknown"
    first_person = bool(re.search(r"\b(?:я|мы|мне|мой|i|we|my|our)\b", text, flags=re.IGNORECASE))
    formal_markers = len(re.findall(
        r"\b(?:следовательно|таким образом|исследован|метод|результат|therefore|method|analysis|result)\b",
        text,
        flags=re.IGNORECASE,
    ))
    long_words = sum(1 for word in words if len(word) >= 9)
    density = round(long_words / len(words), 3)
    has_bullets = bool(re.search(r"^\s*[-*]\s+", text, flags=re.MULTILINE))
    has_numbered = bool(re.search(r"^\s*\d+[.)]\s+", text, flags=re.MULTILINE))
    return StyleProfile(
        sample_origin=origin,
        language=language,
        formality="formal" if formal_markers >= 2 or density >= 0.18 else "personal" if first_person else "neutral",
        terminology_density=density,
        paragraph_words=average,
        heading_preference="markdown" if re.search(r"^#{1,6}\s+", text, flags=re.MULTILINE) else "none",
        list_preference="mixed" if has_bullets and has_numbered else "bulleted" if has_bullets else "numbered" if has_numbered else "none",
        first_person_allowed=first_person,
        transition_style="explicit" if formal_markers else "implicit",
    )
