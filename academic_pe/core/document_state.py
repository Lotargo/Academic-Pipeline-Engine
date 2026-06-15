from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from academic_pe.core.continuation import is_terminal_section_name
from academic_pe.core.document_structure import (
    HeadingPolicy,
    SemanticRole,
    section_heading_policy,
    section_semantic_role,
)


class HeadingNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1)
    level: int = Field(..., ge=1)
    section_name: str = Field(..., min_length=1)
    source: str = "section"
    heading_policy: str = HeadingPolicy.render_required.value
    semantic_role: str = SemanticRole.body.value


class ReferenceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_text: str = Field(..., min_length=1)
    normalized_key: str = Field(..., min_length=1)
    style: str = "unknown"
    marker: str = ""
    section_name: str = Field(..., min_length=1)


class StructuralLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label_type: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    section_name: str = Field(..., min_length=1)


class StyleProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language_hint: str = "unknown"
    register_hint: str = "neutral"
    heading_style: str = "unknown"
    citation_style: str = "none"
    average_paragraph_words: float = 0.0
    has_markdown_headings: bool = False
    has_numbered_headings: bool = False
    has_latex_formulas: bool = False
    list_style: str = "none"


class ContinuityDossier(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_stopping_point: str = ""
    section_order: List[str] = Field(default_factory=list)
    terminal_sections: List[str] = Field(default_factory=list)
    visible_headings: List[str] = Field(default_factory=list)
    terminology: List[str] = Field(default_factory=list)
    style_summary: str = ""
    reference_summary: str = ""


class DocumentSectionState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    content: str = ""
    semantic_role: str = SemanticRole.body.value
    heading_policy: str = HeadingPolicy.render_required.value
    is_terminal: bool = False


class DocumentState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_sections: List[DocumentSectionState] = Field(default_factory=list)
    rendered_body: Dict[str, str] = Field(default_factory=dict)
    terminal_sections: List[str] = Field(default_factory=list)
    headings: List[str] = Field(default_factory=list)
    heading_tree: List[HeadingNode] = Field(default_factory=list)
    reference_registry: List[ReferenceEntry] = Field(default_factory=list)
    structural_labels: List[StructuralLabel] = Field(default_factory=list)
    style_profile: StyleProfile = Field(default_factory=StyleProfile)
    continuity_dossier: ContinuityDossier = Field(default_factory=ContinuityDossier)
    runtime_manifest: Dict[str, Any] = Field(default_factory=dict)


def extract_document_state(continuation_source: Optional[Dict[str, Any]]) -> DocumentState:
    if not continuation_source:
        return DocumentState()

    runtime_sections = _runtime_template_sections(continuation_source)
    runtime_by_name = {
        str(section.get("name")): section
        for section in runtime_sections
        if isinstance(section, dict) and section.get("name")
    }

    sections: List[DocumentSectionState] = []
    context = continuation_source.get("context")
    if isinstance(context, dict):
        for name, raw_content in context.items():
            if name == "document_plan":
                continue
            runtime_section = runtime_by_name.get(str(name), {})
            content = str(raw_content or "")
            section = _section_state_from_raw(str(name), content, runtime_section)
            sections.append(section)
    else:
        for raw_section in runtime_sections:
            if isinstance(raw_section, dict) and raw_section.get("name"):
                sections.append(_section_state_from_raw(str(raw_section["name"]), "", raw_section))

    terminal_sections = [section.name for section in sections if section.is_terminal]
    heading_tree = _extract_heading_tree(sections)
    reference_registry = _extract_reference_registry(sections)
    structural_labels = _extract_structural_labels(sections)
    style_profile = _extract_style_profile(sections, heading_tree, reference_registry)
    return DocumentState(
        source_sections=sections,
        rendered_body={section.name: section.content for section in sections},
        terminal_sections=terminal_sections,
        headings=[section.title for section in sections],
        heading_tree=heading_tree,
        reference_registry=reference_registry,
        structural_labels=structural_labels,
        style_profile=style_profile,
        continuity_dossier=_build_continuity_dossier(
            sections,
            terminal_sections,
            heading_tree,
            reference_registry,
            style_profile,
        ),
        runtime_manifest=_runtime_manifest_metadata(continuation_source),
    )


def _section_state_from_raw(name: str, content: str, runtime_section: Dict[str, Any]) -> DocumentSectionState:
    title = str(runtime_section.get("title") or runtime_section.get("topic") or _humanize_name(name))
    semantic_role = section_semantic_role(runtime_section)
    heading_policy = section_heading_policy(runtime_section)
    is_terminal = (
        semantic_role
        in {
            SemanticRole.reference_section.value,
            SemanticRole.appendix.value,
            SemanticRole.glossary.value,
        }
        or is_terminal_section_name(name)
        or is_terminal_section_name(title)
    )
    return DocumentSectionState(
        name=name,
        title=title,
        content=content,
        semantic_role=semantic_role,
        heading_policy=heading_policy,
        is_terminal=is_terminal,
    )


def _runtime_template_sections(continuation_source: Dict[str, Any]) -> List[dict]:
    runtime_template = continuation_source.get("runtime_template")
    if not isinstance(runtime_template, dict):
        return []
    sections = runtime_template.get("sections")
    if not isinstance(sections, list):
        return []
    return [section for section in sections if isinstance(section, dict)]


def _runtime_manifest_metadata(continuation_source: Dict[str, Any]) -> Dict[str, Any]:
    runtime_prompt_manifest = continuation_source.get("runtime_prompt_manifest")
    if not isinstance(runtime_prompt_manifest, dict):
        return {}
    metadata = runtime_prompt_manifest.get("metadata")
    return dict(metadata) if isinstance(metadata, dict) else {}


def _humanize_name(name: str) -> str:
    return re.sub(r"[_-]+", " ", name).strip().title()


def _extract_heading_tree(sections: List[DocumentSectionState]) -> List[HeadingNode]:
    headings: List[HeadingNode] = []
    for section in sections:
        if section.heading_policy != HeadingPolicy.internal_only.value:
            headings.append(
                HeadingNode(
                    title=section.title,
                    level=1,
                    section_name=section.name,
                    source="section",
                    heading_policy=section.heading_policy,
                    semantic_role=section.semantic_role,
                )
            )
        for match in re.finditer(r"^(#{1,6})\s+(.+?)\s*$", section.content, flags=re.MULTILINE):
            title = match.group(2).strip()
            if title:
                headings.append(
                    HeadingNode(
                        title=title,
                        level=len(match.group(1)),
                        section_name=section.name,
                        source="markdown",
                        heading_policy=section.heading_policy,
                        semantic_role=section.semantic_role,
                    )
                )
    return headings


def _extract_reference_registry(sections: List[DocumentSectionState]) -> List[ReferenceEntry]:
    entries: List[ReferenceEntry] = []
    seen = set()
    for section in sections:
        if not section.is_terminal and section.semantic_role != SemanticRole.reference_section.value:
            continue
        for line in section.content.splitlines():
            parsed = _parse_reference_line(line)
            if not parsed:
                continue
            raw_text, marker, style = parsed
            key = _normalize_reference_key(raw_text)
            if not key or key in seen:
                continue
            seen.add(key)
            entries.append(
                ReferenceEntry(
                    raw_text=raw_text,
                    normalized_key=key,
                    marker=marker,
                    style=style,
                    section_name=section.name,
                )
            )
    return entries


def _parse_reference_line(line: str) -> Optional[tuple[str, str, str]]:
    cleaned = line.strip()
    if not cleaned:
        return None

    numbered = re.match(r"^\[(\d+)\]\s+(.+)$", cleaned)
    if numbered:
        return cleaned, numbered.group(1), "numbered"

    numbered = re.match(r"^(\d+)[.)]\s+(.+)$", cleaned)
    if numbered:
        return cleaned, numbered.group(1), "numbered"

    bullet = re.match(r"^[-*]\s+(.+)$", cleaned)
    if bullet:
        body = bullet.group(1).strip()
        style = "author_year" if _AUTHOR_YEAR_RE.search(body) else "bullet"
        return body, "", style

    if _AUTHOR_YEAR_RE.search(cleaned):
        return cleaned, "", "author_year"

    return None


def _normalize_reference_key(text: str) -> str:
    value = re.sub(r"^\s*(?:\[\d+\]|\d+[.)]|[-*])\s*", "", text.strip())
    value = re.sub(r"\s+", " ", value).strip().lower()
    return value


def _extract_structural_labels(sections: List[DocumentSectionState]) -> List[StructuralLabel]:
    labels: List[StructuralLabel] = []
    seen = set()
    patterns = [
        ("table", r"\b(?:table|таблица)\s+(\d+(?:\.\d+)*)\b"),
        ("figure", r"\b(?:figure|fig\.|рисунок|рис\.)\s+(\d+(?:\.\d+)*)\b"),
        ("formula", r"(?<!\w)\((\d+(?:\.\d+)*)\)"),
    ]
    for section in sections:
        for label_type, pattern in patterns:
            for match in re.finditer(pattern, section.content, flags=re.IGNORECASE):
                label = match.group(1)
                key = (label_type, label, section.name)
                if key in seen:
                    continue
                seen.add(key)
                labels.append(
                    StructuralLabel(
                        label_type=label_type,
                        label=label,
                        section_name=section.name,
                    )
                )
    return labels


def _extract_style_profile(
    sections: List[DocumentSectionState],
    heading_tree: List[HeadingNode],
    reference_registry: List[ReferenceEntry],
) -> StyleProfile:
    text = "\n\n".join(section.content for section in sections if section.content.strip())
    paragraph_lengths = [
        len(re.findall(r"\w+", paragraph, flags=re.UNICODE))
        for paragraph in re.split(r"\n\s*\n", text)
        if paragraph.strip()
    ]
    average_paragraph_words = (
        round(sum(paragraph_lengths) / len(paragraph_lengths), 1)
        if paragraph_lengths
        else 0.0
    )
    citation_style = _dominant_reference_style(reference_registry)
    return StyleProfile(
        language_hint=_language_hint(text),
        register_hint=_register_hint(text, average_paragraph_words),
        heading_style=_heading_style(heading_tree),
        citation_style=citation_style,
        average_paragraph_words=average_paragraph_words,
        has_markdown_headings=any(heading.source == "markdown" for heading in heading_tree),
        has_numbered_headings=any(re.match(r"^\d+(?:\.\d+)*\.?\s+", heading.title) for heading in heading_tree),
        has_latex_formulas=bool(re.search(r"(\$\$.*?\$\$|\\\(|\\\[|\\begin\{equation\})", text, flags=re.DOTALL)),
        list_style=_list_style(text),
    )


def _dominant_reference_style(reference_registry: List[ReferenceEntry]) -> str:
    if not reference_registry:
        return "none"
    counts: Dict[str, int] = {}
    for entry in reference_registry:
        counts[entry.style] = counts.get(entry.style, 0) + 1
    return max(counts.items(), key=lambda item: item[1])[0]


def _language_hint(text: str) -> str:
    cyrillic = len(re.findall(r"[А-Яа-яЁё]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    if cyrillic > latin:
        return "ru"
    if latin > 0:
        return "en"
    return "unknown"


def _register_hint(text: str, average_paragraph_words: float) -> str:
    lower = text.lower()
    if re.search(r"\b(я|мы|мне|мой|i|we|my|our)\b", lower) and average_paragraph_words < 70:
        return "personal_or_narrative"
    if re.search(r"\b(исследован|рассмотрен|метод|анализ|результат|therefore|method|analysis|result)\b", lower):
        return "academic_or_technical"
    return "neutral"


def _heading_style(heading_tree: List[HeadingNode]) -> str:
    if not heading_tree:
        return "none"
    if any(heading.source == "markdown" for heading in heading_tree):
        return "markdown"
    if any(re.match(r"^\d+(?:\.\d+)*\.?\s+", heading.title) for heading in heading_tree):
        return "numbered"
    return "section_titles"


def _list_style(text: str) -> str:
    has_bullets = bool(re.search(r"^\s*[-*]\s+", text, flags=re.MULTILINE))
    has_numbered = bool(re.search(r"^\s*\d+[.)]\s+", text, flags=re.MULTILINE))
    if has_bullets and has_numbered:
        return "mixed"
    if has_numbered:
        return "numbered"
    if has_bullets:
        return "bulleted"
    return "none"


def _build_continuity_dossier(
    sections: List[DocumentSectionState],
    terminal_sections: List[str],
    heading_tree: List[HeadingNode],
    reference_registry: List[ReferenceEntry],
    style_profile: StyleProfile,
) -> ContinuityDossier:
    visible_headings = [
        heading.title
        for heading in heading_tree
        if heading.heading_policy != HeadingPolicy.internal_only.value
    ]
    return ContinuityDossier(
        current_stopping_point=_current_stopping_point(sections),
        section_order=[section.name for section in sections],
        terminal_sections=terminal_sections,
        visible_headings=visible_headings,
        terminology=_extract_terminology(sections),
        style_summary=(
            f"language={style_profile.language_hint}; register={style_profile.register_hint}; "
            f"heading_style={style_profile.heading_style}; citation_style={style_profile.citation_style}"
        ),
        reference_summary=(
            f"{len(reference_registry)} reference(s), style={style_profile.citation_style}"
            if reference_registry
            else "no references detected"
        ),
    )


def _current_stopping_point(sections: List[DocumentSectionState]) -> str:
    for section in reversed(sections):
        if section.is_terminal:
            continue
        paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", section.content) if paragraph.strip()]
        if paragraphs:
            return _clip_text(paragraphs[-1], 360)
    return ""


def _extract_terminology(sections: List[DocumentSectionState]) -> List[str]:
    text = "\n".join(section.content for section in sections)
    candidates = re.findall(r"\b[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё0-9-]{3,}(?:\s+[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё0-9-]{3,}){0,2}\b", text)
    seen = set()
    terms: List[str] = []
    for candidate in candidates:
        normalized = candidate.strip()
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        terms.append(normalized)
        if len(terms) >= 12:
            break
    return terms


def _clip_text(text: str, max_chars: int) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 1].rstrip() + "..."


_AUTHOR_YEAR_RE = re.compile(r"\b[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё-]+(?:\s+[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё-]+)*\s*\(\d{4}[a-zа-я]?\)")
