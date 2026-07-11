from __future__ import annotations

import re

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from academic_pe.core.config import SectionPrompt
from academic_pe.core.document_assembly import CoverageMatrix, build_coverage_matrix


class SectionBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: str = Field(..., min_length=1)
    purpose: str = Field(..., min_length=1)
    owned_claims: list[str] = Field(default_factory=list)
    required_inputs: list[str] = Field(default_factory=list)
    allowed_sources: list[str] = Field(default_factory=list)
    calculations: list[str] = Field(default_factory=list)
    terms_to_preserve: list[str] = Field(default_factory=list)
    must_not_repeat: list[str] = Field(default_factory=list)
    incoming_transition: str | None = None
    outgoing_handoff: str | None = None
    visible_heading: bool = True
    output_form: str = "section prose"
    writing_constraints: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _owned_content_is_not_repeated(self) -> "SectionBrief":
        overlap = set(self.owned_claims) & set(self.must_not_repeat)
        if overlap:
            raise ValueError(f"owned responsibilities cannot be marked as repetitions: {', '.join(sorted(overlap))}")
        return self


_INTERNAL_LINE = re.compile(
    r"(?:\[(?:active |template |grep |document plan|context data|original task|draft output)|"
    r"\bUSE_GREP\s*:|<<<<<<<\s*REPLACE|^>>>>>>>$|\bNO_CHANGES\b)",
    re.IGNORECASE,
)


def _coverage_for_section(
    section: SectionPrompt,
    coverage: Mapping[str, Any] | CoverageMatrix | None,
    section_names: Sequence[str] | None,
) -> tuple[list[str], list[str]]:
    if coverage is None and section_names is None:
        return [], []
    names = list(section_names or [section.name])
    if section.name not in names:
        names.append(section.name)
    matrix = build_coverage_matrix(coverage, names)
    owned = [responsibility for responsibility, owners in matrix.coverage.items() if section.name in owners]
    owned_elsewhere = [responsibility for responsibility, owners in matrix.coverage.items() if section.name not in owners]
    return owned, owned_elsewhere


def compile_section_brief(
    section: SectionPrompt,
    *,
    coverage: Mapping[str, Any] | CoverageMatrix | None = None,
    section_names: Sequence[str] | None = None,
    required_inputs: Sequence[str] = (),
    allowed_sources: Sequence[str] = (),
    calculations: Sequence[str] = (),
    terms_to_preserve: Sequence[str] = (),
) -> SectionBrief:
    """Compile legacy section configuration into bounded Writer-facing instructions."""
    constraints = []
    for raw_line in (section.instruction or "").splitlines():
        line = " ".join(raw_line.split()).strip(" -\t")
        if line and not _INTERNAL_LINE.search(line):
            constraints.append(line)

    owned_claims, owned_elsewhere = _coverage_for_section(section, coverage, section_names)
    visible_heading = section.heading_policy != "internal_only"
    output_form = "section prose with a visible heading" if visible_heading else "section prose without a heading"
    return SectionBrief(
        section_id=section.name,
        purpose=section.topic or section.name,
        owned_claims=owned_claims,
        required_inputs=list(dict.fromkeys(required_inputs)),
        allowed_sources=list(dict.fromkeys(allowed_sources)),
        calculations=list(dict.fromkeys(calculations)),
        terms_to_preserve=list(dict.fromkeys(terms_to_preserve)),
        must_not_repeat=owned_elsewhere,
        visible_heading=visible_heading,
        output_form=output_form,
        writing_constraints=list(dict.fromkeys(constraints)),
    )
