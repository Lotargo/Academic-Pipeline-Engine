from __future__ import annotations

import re


_CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
_LATIN_RE = re.compile(r"[A-Za-z]")
_EXPLICIT_LANGUAGE_PATTERNS = [
    (
        "zh",
        re.compile(
            r"(?:write|written|answer|respond|document|text)\s+(?:it\s+)?(?:in\s+)?(?:chinese|mandarin)"
            r"|(?:написать|пиши|документ|текст|ответ)\s+(?:на\s+)?китайском",
            re.IGNORECASE,
        ),
    ),
    (
        "en",
        re.compile(
            r"(?:write|written|answer|respond|document|text)\s+(?:it\s+)?(?:in\s+)?english"
            r"|(?:написать|пиши|документ|текст|ответ)\s+(?:на\s+)?английском",
            re.IGNORECASE,
        ),
    ),
    (
        "ru",
        re.compile(
            r"(?:write|written|answer|respond|document|text)\s+(?:it\s+)?(?:in\s+)?russian"
            r"|(?:написать|пиши|документ|текст|ответ)\s+(?:на\s+)?русском",
            re.IGNORECASE,
        ),
    ),
]


def detect_language(text: str) -> str:
    if not text:
        return "en"

    cyrillic = len(_CYRILLIC_RE.findall(text))
    latin = len(_LATIN_RE.findall(text))

    if cyrillic > latin * 0.6 and cyrillic >= 8:
        return "ru"
    return "en"


def resolve_output_language(prompt_text: str, configured_language: str = "auto") -> str:
    if configured_language != "auto":
        return configured_language

    explicit_language = detect_explicit_output_language(prompt_text)
    if explicit_language:
        return explicit_language

    return detect_language(prompt_text)


def detect_explicit_output_language(text: str) -> str | None:
    if not text:
        return None

    for language, pattern in _EXPLICIT_LANGUAGE_PATTERNS:
        if pattern.search(text):
            return language
    return None


def language_instruction(language: str) -> str:
    if language == "ru":
        return (
            "Write the entire document in Russian. Every section, heading, plan item, "
            "and review note must be in Russian unless the user explicitly requested "
            "another language for a quoted term or example."
        )
    if language == "zh":
        return (
            "Write the entire document in Chinese. Every section, heading, plan item, "
            "and review note must be in Chinese unless the user explicitly requested "
            "another language for a quoted term or example."
        )
    return (
        "Write the entire document in English. Every section, heading, plan item, "
        "and review note must be in English unless the user explicitly requested "
        "another language for a quoted term or example."
    )
