from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional

from academic_pe.core.document_structure import SemanticRole, section_semantic_role


class ContinuationIntent(str, Enum):
    continue_append = "continue_append"
    bridge_and_continue = "bridge_and_continue"
    revise_in_place = "revise_in_place"
    expand_section = "expand_section"
    complete_missing_section = "complete_missing_section"
    update_references_only = "update_references_only"
    restructure = "restructure"


@dataclass(frozen=True)
class ContinuationIntentResolution:
    intent: ContinuationIntent
    reason: str
    confidence: float
    signals: List[str]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["intent"] = self.intent.value
        return data


_RESTRUCTURE_PATTERNS = [
    r"\brestructure\b",
    r"\breorganize\b",
    r"\brebuild\b",
    r"\bchange\s+structure\b",
    r"\u043f\u0435\u0440\u0435\u0441\u0442\u0440\u0443\u043a\u0442\u0443\u0440",
    r"\u043f\u0435\u0440\u0435\u0441\u043e\u0431\u0435\u0440",
]
_REFERENCE_PATTERNS = [
    r"\b(?:add|update|merge|dedupe|deduplicate|rebuild)\s+(?:the\s+)?(?:sources?|references?|bibliograph)",
    r"\breferences?\b",
    r"\bbibliograph",
    r"\bworks\s+cited\b",
    r"\bcitations?\b",
    r"\u0441\u043f\u0438\u0441\u043e\u043a\s+\u043b\u0438\u0442\u0435\u0440\u0430\u0442\u0443\u0440",
    r"\u0431\u0438\u0431\u043b\u0438\u043e\u0433\u0440\u0430\u0444",
    r"\u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a",
]
_COMPLETE_MISSING_PATTERNS = [
    r"\bfinish\b",
    r"\bcomplete\b",
    r"\bfill\s+(?:the\s+)?(?:missing\s+)?(?:section|gap)\b",
    r"\bwrite\s+(?:the\s+)?conclusion\b",
    r"\u0434\u043e\u043f\u0438\u0448",
    r"\u0437\u0430\u043a\u043e\u043d\u0447",
    r"\u0437\u0430\u0432\u0435\u0440\u0448",
]
_EXPAND_SECTION_PATTERNS = [
    r"\bexpand\b",
    r"\badd\s+(?:to|more\s+to|details?\s+to)\b",
    r"\badd\s+(?:the\s+)?(?:next\s+)?(?:analysis|section|chapter|part)\b",
    r"\bchapter\s+\d+\b",
    r"\bsection\s+\d+\b",
    r"\bpart\s+\d+\b",
    r"\u0440\u0430\u0441\u0448\u0438\u0440",
    r"\u0434\u043e\u0431\u0430\u0432.*\u0432\s+(?:\u0433\u043b\u0430\u0432|\u0440\u0430\u0437\u0434\u0435\u043b)",
    r"\u0433\u043b\u0430\u0432[ауеы]\s+\d+",
    r"\u0440\u0430\u0437\u0434\u0435\u043b\s+\d+",
]
_REVISE_PATTERNS = [
    r"\bimprove\b",
    r"\brevise\b",
    r"\brewrite\b",
    r"\bedit\b",
    r"\bfix\b",
    r"\bpolish\b",
    r"\u0443\u043b\u0443\u0447\u0448",
    r"\u0438\u0441\u043f\u0440\u0430\u0432",
    r"\u043f\u0435\u0440\u0435\u043f\u0438\u0448",
    r"\u043e\u0442\u0440\u0435\u0434\u0430\u043a\u0442",
]
_CONTINUE_PATTERNS = [
    r"\bcontinue\b",
    r"\bgo\s+on\b",
    r"\bkeep\s+going\b",
    r"\u043f\u0440\u043e\u0434\u043e\u043b",
]

_TERMINAL_SECTION_ALIASES = {
    "references",
    "reference",
    "bibliography",
    "works cited",
    "sources",
    "appendix",
    "appendices",
    "glossary",
    "author notes",
    "export metadata",
    "\u0441\u043f\u0438\u0441\u043e\u043a \u043b\u0438\u0442\u0435\u0440\u0430\u0442\u0443\u0440\u044b",
    "\u043b\u0438\u0442\u0435\u0440\u0430\u0442\u0443\u0440\u0430",
    "\u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a\u0438",
    "\u043f\u0440\u0438\u043b\u043e\u0436\u0435\u043d\u0438\u044f",
    "\u043f\u0440\u0438\u043b\u043e\u0436\u0435\u043d\u0438\u0435",
    "\u0433\u043b\u043e\u0441\u0441\u0430\u0440\u0438\u0439",
}
_HARD_ENDING_SECTION_ALIASES = {
    "conclusion",
    "summary",
    "ending",
    "finale",
    "\u0437\u0430\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u0435",
    "\u0432\u044b\u0432\u043e\u0434",
    "\u0432\u044b\u0432\u043e\u0434\u044b",
    "\u0444\u0438\u043d\u0430\u043b",
}
_HARD_ENDING_TEXT_RE = re.compile(
    r"(\bthe\s+end\b|\bin\s+conclusion\b|\bto\s+conclude\b|\boverall\b|\btherefore\b|"
    r"\u0432\s+\u0437\u0430\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u0435|"
    r"\u043f\u043e\u0434\u0432\u0435\u0434\u0435\u043c\s+\u0438\u0442\u043e\u0433|"
    r"\u0432\s+\u0438\u0442\u043e\u0433\u0435)",
    re.IGNORECASE,
)


def infer_continuation_intent(
    *,
    topic: str = "",
    instructions: str = "",
    continuation_source: Optional[Dict[str, Any]] = None,
) -> Optional[ContinuationIntentResolution]:
    if not continuation_source:
        return None

    override = str(continuation_source.get("intent_override") or "").strip()
    if override:
        try:
            intent = ContinuationIntent(override)
        except ValueError:
            intent = None
        if intent is not None:
            return _resolution(
                intent,
                "User selected a continuation intent override.",
                0.99,
                ["user_intent_override"],
            )

    request_text = " ".join(part.strip() for part in [topic or "", instructions or ""] if part and part.strip())
    normalized = request_text.lower()

    if _matches_any(normalized, _RESTRUCTURE_PATTERNS):
        return _resolution(
            ContinuationIntent.restructure,
            "User explicitly asked to change or rebuild the document structure.",
            0.86,
            ["restructure_keyword"],
        )

    if _matches_any(normalized, _COMPLETE_MISSING_PATTERNS):
        return _resolution(
            ContinuationIntent.complete_missing_section,
            "User asked to finish or complete a missing/final section.",
            0.74,
            ["complete_keyword"],
        )

    if _matches_any(normalized, _EXPAND_SECTION_PATTERNS):
        return _resolution(
            ContinuationIntent.expand_section,
            "User asked to expand a specific existing part of the document.",
            0.78,
            ["expand_keyword"],
        )

    if _matches_any(normalized, _REVISE_PATTERNS):
        return _resolution(
            ContinuationIntent.revise_in_place,
            "User asked to improve or rewrite the current artifact rather than append new scope.",
            0.8,
            ["revise_keyword"],
        )

    if _is_references_only_request(normalized):
        return _resolution(
            ContinuationIntent.update_references_only,
            "User request is primarily about sources, citations, or bibliography.",
            0.78,
            ["reference_keyword"],
        )

    has_explicit_continue = _matches_any(normalized, _CONTINUE_PATTERNS)
    has_sparse_request = not normalized or normalized in {"continue", "\u043f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u0442\u044c"}
    if has_explicit_continue or has_sparse_request:
        if source_has_hard_ending(continuation_source):
            return _resolution(
                ContinuationIntent.bridge_and_continue,
                "The source appears to end with a conclusion or closed ending, so continuation needs a bridge.",
                0.72,
                ["continue_keyword", "hard_ending_source"],
            )
        return _resolution(
            ContinuationIntent.continue_append,
            "Default continuation without revision instructions should append after the natural current endpoint.",
            0.7,
            ["continue_keyword"],
        )

    return _resolution(
        ContinuationIntent.continue_append,
        "Continuation source is present and no stronger edit intent was detected.",
        0.58,
        ["continuation_source"],
    )


def detect_terminal_sections(continuation_source: Optional[Dict[str, Any]]) -> List[str]:
    if not continuation_source:
        return []

    terminal_names: List[str] = []
    for section in _source_sections(continuation_source):
        name = str(section.get("name") or "")
        title = str(section.get("title") or section.get("topic") or "")
        role = section_semantic_role(section)
        if role in {
            SemanticRole.reference_section.value,
            SemanticRole.appendix.value,
            SemanticRole.glossary.value,
        } or is_terminal_section_name(name) or is_terminal_section_name(title):
            terminal_names.append(name)

    return _dedupe_preserving_order([name for name in terminal_names if name])


def source_has_hard_ending(continuation_source: Optional[Dict[str, Any]]) -> bool:
    if not continuation_source:
        return False

    sections = _source_sections(continuation_source)
    body_sections = [
        section
        for section in sections
        if not is_terminal_section_name(str(section.get("name") or ""))
        and not is_terminal_section_name(str(section.get("title") or section.get("topic") or ""))
    ]
    if not body_sections:
        body_sections = sections
    if not body_sections:
        return False

    last = body_sections[-1]
    if is_hard_ending_section_name(str(last.get("name") or "")) or is_hard_ending_section_name(
        str(last.get("title") or last.get("topic") or "")
    ):
        return True

    text = str(last.get("content") or "").strip()
    return bool(text and _HARD_ENDING_TEXT_RE.search(text[-1200:]))


def is_terminal_section_name(name: str) -> bool:
    normalized = _normalize_heading_name(name)
    return (
        normalized in _TERMINAL_SECTION_ALIASES
        or normalized.startswith("appendix ")
        or normalized.startswith("\u043f\u0440\u0438\u043b\u043e\u0436\u0435\u043d\u0438\u0435 ")
    )


def is_hard_ending_section_name(name: str) -> bool:
    return _normalize_heading_name(name) in _HARD_ENDING_SECTION_ALIASES


def _source_sections(continuation_source: Dict[str, Any]) -> List[dict]:
    runtime_sections = _runtime_template_sections(continuation_source)
    runtime_by_name = {
        str(section.get("name")): section
        for section in runtime_sections
        if isinstance(section, dict) and section.get("name")
    }

    context = continuation_source.get("context")
    sections: List[dict] = []
    if isinstance(context, dict):
        for name, content in context.items():
            if name == "document_plan":
                continue
            runtime_section = runtime_by_name.get(str(name), {})
            sections.append(
                {
                    "name": str(name),
                    "title": runtime_section.get("title") or runtime_section.get("topic") or _humanize_name(str(name)),
                    "topic": runtime_section.get("topic"),
                    "semantic_role": runtime_section.get("semantic_role"),
                    "heading_policy": runtime_section.get("heading_policy"),
                    "content": content,
                }
            )
        return sections

    return [
        {
            "name": str(section.get("name") or ""),
            "title": section.get("title"),
            "topic": section.get("topic"),
            "semantic_role": section.get("semantic_role"),
            "heading_policy": section.get("heading_policy"),
            "content": "",
        }
        for section in runtime_sections
        if isinstance(section, dict)
    ]


def _runtime_template_sections(continuation_source: Dict[str, Any]) -> List[dict]:
    runtime_template = continuation_source.get("runtime_template")
    if not isinstance(runtime_template, dict):
        return []
    sections = runtime_template.get("sections")
    if not isinstance(sections, list):
        return []
    return [section for section in sections if isinstance(section, dict)]


def _matches_any(text: str, patterns: Iterable[str]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _is_references_only_request(text: str) -> bool:
    if not _matches_any(text, _REFERENCE_PATTERNS):
        return False
    body_edit_patterns = [
        *_CONTINUE_PATTERNS,
        *_EXPAND_SECTION_PATTERNS,
        *_COMPLETE_MISSING_PATTERNS,
        *_REVISE_PATTERNS,
        r"\bnext\s+(?:analysis|section|chapter|part)\b",
        r"\bbody\s+content\b",
    ]
    return not _matches_any(text, body_edit_patterns)


def _resolution(
    intent: ContinuationIntent,
    reason: str,
    confidence: float,
    signals: List[str],
) -> ContinuationIntentResolution:
    return ContinuationIntentResolution(
        intent=intent,
        reason=reason,
        confidence=confidence,
        signals=signals,
    )


def _normalize_heading_name(name: str) -> str:
    text = re.sub(r"^\s*\d+(?:[.)]\d+)*[.)]?\s*", "", name or "")
    text = re.sub(r"[*_`#]+", "", text)
    text = re.sub(r"[\W_]+", " ", text, flags=re.UNICODE)
    return text.strip().lower()


def _humanize_name(name: str) -> str:
    return re.sub(r"[_-]+", " ", name).strip().title()


def _dedupe_preserving_order(values: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
