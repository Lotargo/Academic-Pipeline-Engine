from __future__ import annotations

from enum import Enum
from typing import Any, Iterable, List


class HeadingPolicy(str, Enum):
    render_required = "render_required"
    render_allowed = "render_allowed"
    internal_only = "internal_only"
    inherit_source = "inherit_source"
    user_mandated = "user_mandated"


class SemanticRole(str, Enum):
    body = "body"
    chapter = "chapter"
    academic_section = "academic_section"
    narrative_beat = "narrative_beat"
    editorial_note = "editorial_note"
    reference_section = "reference_section"
    appendix = "appendix"
    glossary = "glossary"


def section_heading_policy(section: Any) -> str:
    value: Any = None
    if isinstance(section, dict):
        value = section.get("heading_policy")
    else:
        value = getattr(section, "heading_policy", None)

    value = getattr(value, "value", value)
    if not value:
        return HeadingPolicy.render_required.value
    return str(value)


def section_semantic_role(section: Any) -> str:
    value: Any = None
    if isinstance(section, dict):
        value = section.get("semantic_role")
    else:
        value = getattr(section, "semantic_role", None)

    value = getattr(value, "value", value)
    if not value:
        return SemanticRole.body.value
    return str(value)


def is_renderable_section(section: Any) -> bool:
    return section_heading_policy(section) != HeadingPolicy.internal_only.value


def renderable_sections(sections: Iterable[Any]) -> List[Any]:
    return [section for section in sections if is_renderable_section(section)]
