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
    return DocumentState(
        source_sections=sections,
        rendered_body={section.name: section.content for section in sections},
        terminal_sections=terminal_sections,
        headings=[section.title for section in sections],
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
