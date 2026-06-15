from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from academic_pe.core.config import QualityGateConfig


@dataclass
class GateResult:
    passed: bool
    issues: List[str] = field(default_factory=list)


def check_volume(context: Dict[str, str], cfg: QualityGateConfig) -> GateResult:
    if not cfg.volume.enabled:
        return GateResult(passed=True)

    issues: List[str] = []
    for name, text in context.items():
        text = text or ""
        char_count = len(text)
        if char_count < cfg.volume.min_chars:
            issues.append(
                f"Section '{name}' too short: {char_count} chars "
                f"(min {cfg.volume.min_chars})"
            )
    return GateResult(passed=len(issues) == 0, issues=issues)


def _find_tex_blocks(text: str) -> List[str]:
    blocks: List[str] = []
    pos = 0
    while pos < len(text):
        dollar = text.find("$", pos)
        if dollar == -1:
            break
        if dollar + 1 < len(text) and text[dollar + 1] == "$":
            end = text.find("$$", dollar + 2)
            if end == -1:
                blocks.append(text[dollar:])
                break
            blocks.append(text[dollar:end + 2])
            pos = end + 2
        else:
            end = text.find("$", dollar + 1)
            if end == -1:
                blocks.append(text[dollar:])
                break
            blocks.append(text[dollar:end + 1])
            pos = end + 1
    return blocks


def _balanced_braces(s: str) -> bool:
    depth = 0
    for ch in s:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def check_latex(context: Dict[str, str], cfg: QualityGateConfig) -> GateResult:
    if not cfg.latex.enabled:
        return GateResult(passed=True)

    issues: List[str] = []
    for name, text in context.items():
        text = text or ""
        blocks = _find_tex_blocks(text)

        for block in blocks:
            inner = block.strip("$")

            if not _balanced_braces(inner):
                issues.append(
                    f"Section '{name}' has unbalanced braces in: {block[:40]}..."
                )

            if inner.count("\\begin") != inner.count("\\end"):
                issues.append(
                    f"Section '{name}' has unmatched \\begin/\\end in: {block[:40]}..."
                )
    return GateResult(passed=len(issues) == 0, issues=issues)

def check_markdown_artifacts(context: Dict[str, str], cfg: QualityGateConfig) -> GateResult:
    markdown_cfg = getattr(cfg, "markdown", None)
    if markdown_cfg is not None and not markdown_cfg.enabled:
        return GateResult(passed=True)

    issues: List[str] = []
    for name, text in context.items():
        text = text or ""
        lines = text.splitlines()
        for idx, line in enumerate(lines, 1):
            if line.strip().startswith("```"):
                issues.append(
                    f"Section '{name}' contains raw code block formatting delimiter '{line.strip()}' at line {idx}."
                )
    return GateResult(passed=len(issues) == 0, issues=issues)


def check_continuation_integrity(
    context: Dict[str, str],
    document_state: Optional[Mapping[str, Any]] = None,
) -> GateResult:
    if not document_state:
        return GateResult(passed=True)

    filtered_context = {k: v for k, v in context.items() if k != "document_plan"}
    issues: List[str] = []
    issues.extend(_body_after_terminal_issues(filtered_context, document_state))
    issues.extend(_internal_planning_label_issues(filtered_context))
    issues.extend(_duplicate_terminal_or_boundary_heading_issues(filtered_context, document_state))
    issues.extend(_duplicate_structural_label_issues(filtered_context))
    issues.extend(_citation_reference_mismatch_issues(filtered_context, document_state))
    issues.extend(_style_profile_drift_issues(filtered_context, document_state))
    return GateResult(passed=len(issues) == 0, issues=issues)


def run_all(
    context: Dict[str, str],
    cfg: QualityGateConfig,
    document_state: Optional[Mapping[str, Any]] = None,
) -> GateResult:
    filtered_context = {k: v for k, v in context.items() if k != "document_plan"}
    combined: List[str] = []
    for check_name, check_fn in [
        ("volume", check_volume),
        ("latex", check_latex),
        ("markdown", check_markdown_artifacts),
    ]:
        result = check_fn(filtered_context, cfg)
        if not result.passed:
            combined.extend(result.issues)
    continuation_result = check_continuation_integrity(filtered_context, document_state)
    if not continuation_result.passed:
        combined.extend(continuation_result.issues)
    return GateResult(passed=len(combined) == 0, issues=combined)


def _body_after_terminal_issues(
    context: Mapping[str, str],
    document_state: Mapping[str, Any],
) -> List[str]:
    terminal_sections = {
        str(section)
        for section in document_state.get("terminal_sections", [])
        if str(section)
    }
    if not terminal_sections:
        return []

    issues: List[str] = []
    seen_terminal = ""
    for section_name, text in context.items():
        if not str(text or "").strip():
            continue
        if section_name in terminal_sections:
            seen_terminal = section_name
            continue
        if seen_terminal:
            issues.append(
                f"Section '{section_name}' appears after terminal section '{seen_terminal}'. "
                "Move body content before references, appendices, glossary, or other terminal sections."
            )
    return issues


def _internal_planning_label_issues(context: Mapping[str, str]) -> List[str]:
    issues: List[str] = []
    for section_name, text in context.items():
        for line_no, line in enumerate(str(text or "").splitlines(), 1):
            if _INTERNAL_LABEL_RE.search(line):
                issues.append(
                    f"Section '{section_name}' exposes internal planning label at line {line_no}: "
                    f"{line.strip()[:80]}"
                )
    return issues


def _duplicate_terminal_or_boundary_heading_issues(
    context: Mapping[str, str],
    document_state: Mapping[str, Any],
) -> List[str]:
    aliases = {
        "introduction": {"introduction", "intro", "введение"},
        "conclusion": {"conclusion", "summary", "заключение", "выводы"},
        "references": {"references", "bibliography", "works cited", "список литературы", "источники"},
    }
    counts: Dict[str, List[str]] = {key: [] for key in aliases}

    for section in _source_sections(document_state):
        title = str(section.get("title") or section.get("name") or "")
        normalized = _normalize_heading(title)
        for kind, names in aliases.items():
            if normalized in names:
                counts[kind].append(str(section.get("name") or title))

    for section_name, text in context.items():
        for heading in _markdown_heading_titles(str(text or "")):
            normalized = _normalize_heading(heading)
            for kind, names in aliases.items():
                if normalized in names:
                    counts[kind].append(f"{section_name}:{heading}")

    issues: List[str] = []
    for kind, locations in counts.items():
        unique_locations = _dedupe(locations)
        if len(unique_locations) > 1:
            issues.append(
                f"Duplicate {kind} heading/section detected in {', '.join(unique_locations)}. "
                "Continuation should keep one seamless document structure unless duplication was requested."
            )
    return issues


def _duplicate_structural_label_issues(context: Mapping[str, str]) -> List[str]:
    seen: Dict[tuple[str, str], str] = {}
    issues: List[str] = []
    patterns = [
        ("table", r"\b(?:table|таблица)\s+(\d+(?:\.\d+)*)\b"),
        ("figure", r"\b(?:figure|fig\.|рисунок|рис\.)\s+(\d+(?:\.\d+)*)\b"),
        ("formula", r"(?<!\w)\((\d+(?:\.\d+)*)\)"),
    ]
    for section_name, text in context.items():
        for label_type, pattern in patterns:
            for match in re.finditer(pattern, str(text or ""), flags=re.IGNORECASE):
                key = (label_type, match.group(1))
                if key in seen and seen[key] != section_name:
                    issues.append(
                        f"Duplicate {label_type} label '{match.group(1)}' appears in sections "
                        f"'{seen[key]}' and '{section_name}'. Renumber labels or cross-references coherently."
                    )
                else:
                    seen[key] = section_name
    return _dedupe(issues)


def _citation_reference_mismatch_issues(
    context: Mapping[str, str],
    document_state: Mapping[str, Any],
) -> List[str]:
    reference_count = len(document_state.get("reference_registry", []) or [])
    if reference_count == 0:
        return []

    text = "\n".join(str(value or "") for value in context.values())
    cited_numbers = [
        int(value)
        for value in re.findall(r"(?<!\w)\[(\d{1,3})\](?!\w)", text)
        if value.isdigit()
    ]
    if not cited_numbers:
        return []

    max_citation = max(cited_numbers)
    if max_citation > reference_count:
        return [
            f"Numeric citation [{max_citation}] has no matching reference entry "
            f"(reference registry has {reference_count} entr{'y' if reference_count == 1 else 'ies'})."
        ]
    return []


def _style_profile_drift_issues(
    context: Mapping[str, str],
    document_state: Mapping[str, Any],
) -> List[str]:
    style_profile = document_state.get("style_profile")
    if not isinstance(style_profile, Mapping):
        return []

    source_language = str(style_profile.get("language_hint") or "unknown")
    source_register = str(style_profile.get("register_hint") or "neutral")
    text = "\n\n".join(
        str(value or "")
        for key, value in context.items()
        if key not in set(str(section) for section in document_state.get("terminal_sections", []) or [])
    )
    if not text.strip():
        return []

    issues: List[str] = []
    output_language = _language_hint(text)
    if (
        source_language in {"en", "ru"}
        and output_language in {"en", "ru"}
        and source_language != output_language
    ):
        issues.append(
            f"Continuation language drift detected: source language is '{source_language}', "
            f"but generated body appears to be '{output_language}'. Preserve the source language unless requested."
        )

    output_register = _register_hint(text)
    if source_register == "personal_or_narrative" and output_register == "academic_or_technical":
        issues.append(
            "Continuation register drift detected: source is personal/narrative, "
            "but generated body uses academic or technical register. Preserve narrator, audience level, and voice."
        )
    elif source_register == "academic_or_technical" and output_register == "personal_or_narrative":
        issues.append(
            "Continuation register drift detected: source is academic/technical, "
            "but generated body shifts into personal or narrative register. Preserve the artifact register."
        )

    return issues


def _language_hint(text: str) -> str:
    cyrillic = len(re.findall(r"[А-Яа-яЁё]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    if cyrillic > latin:
        return "ru"
    if latin > 0:
        return "en"
    return "unknown"


def _register_hint(text: str) -> str:
    lower = text.lower()
    if re.search(r"\b(я|мне|мой|моя|i|my|me)\b", lower) and not _ACADEMIC_REGISTER_RE.search(lower):
        return "personal_or_narrative"
    if _ACADEMIC_REGISTER_RE.search(lower):
        return "academic_or_technical"
    return "neutral"


def _source_sections(document_state: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    sections = document_state.get("source_sections", [])
    if not isinstance(sections, list):
        return []
    return [section for section in sections if isinstance(section, Mapping)]


def _markdown_heading_titles(text: str) -> List[str]:
    return [
        match.group(1).strip()
        for match in re.finditer(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", text, flags=re.MULTILINE)
    ]


def _normalize_heading(value: str) -> str:
    normalized = re.sub(r"^\s*\d+(?:\.\d+)*\.?\s+", "", value.strip().lower())
    normalized = re.sub(r"[:：]+$", "", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _dedupe(values: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


_INTERNAL_LABEL_RE = re.compile(
    r"^\s{0,3}(?:#{1,6}\s+|\*\*)?"
    r"(?:exposition|development|conflict analysis|red[_ -]?flags?|risks?|pacing notes?|"
    r"continuity notes?|editorial risks?|internal notes?)"
    r"(?:\*\*)?\s*:?\s*$",
    flags=re.IGNORECASE,
)

_ACADEMIC_REGISTER_RE = re.compile(
    r"\b("
    r"analysis|method|methodology|therefore|hypothesis|dataset|algorithm|"
    r"исследован|рассмотрен|метод|анализ|результат|гипотез|алгоритм"
    r")\b",
    flags=re.IGNORECASE,
)
