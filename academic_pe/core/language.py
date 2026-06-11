from __future__ import annotations

import re


_CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
_LATIN_RE = re.compile(r"[A-Za-z]")


def detect_language(text: str) -> str:
    if not text:
        return "en"

    cyrillic = len(_CYRILLIC_RE.findall(text))
    latin = len(_LATIN_RE.findall(text))

    if cyrillic > latin * 0.6 and cyrillic >= 8:
        return "ru"
    return "en"


def language_instruction(language: str) -> str:
    if language == "ru":
        return "Write the final section in Russian."
    return "Write the final section in English."
