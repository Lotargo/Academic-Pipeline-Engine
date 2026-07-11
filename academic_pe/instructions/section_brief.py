from __future__ import annotations

import re

from pydantic import BaseModel, Field

from academic_pe.core.config import SectionPrompt


class SectionBrief(BaseModel):
    section_id: str = Field(..., min_length=1)
    purpose: str = Field(..., min_length=1)
    owned_claims: list[str] = Field(default_factory=list)
    required_inputs: list[str] = Field(default_factory=list)
    calculations: list[str] = Field(default_factory=list)
    terms_to_preserve: list[str] = Field(default_factory=list)
    must_not_repeat: list[str] = Field(default_factory=list)
    incoming_transition: str | None = None
    outgoing_handoff: str | None = None
    visible_heading: bool = True
    output_form: str = "section prose"
    writing_constraints: list[str] = Field(default_factory=list)


_INTERNAL_LINE = re.compile(
    r"(?:\[(?:active |template |grep |document plan|context data|original task|draft output)|"
    r"\bUSE_GREP\s*:|<<<<<<<\s*REPLACE|^>>>>>>>$|\bNO_CHANGES\b)",
    re.IGNORECASE,
)


def compile_section_brief(section: SectionPrompt) -> SectionBrief:
    """Compile legacy section configuration into bounded Writer-facing instructions."""
    constraints = []
    for raw_line in (section.instruction or "").splitlines():
        line = " ".join(raw_line.split()).strip(" -\t")
        if line and not _INTERNAL_LINE.search(line):
            constraints.append(line)

    visible_heading = section.heading_policy != "internal_only"
    output_form = "section prose with a visible heading" if visible_heading else "section prose without a heading"
    return SectionBrief(
        section_id=section.name,
        purpose=section.topic or section.name,
        visible_heading=visible_heading,
        output_form=output_form,
        writing_constraints=list(dict.fromkeys(constraints)),
    )
