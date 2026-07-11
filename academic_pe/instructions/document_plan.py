from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from academic_pe.core.config import SectionPrompt
from academic_pe.core.document_assembly import build_coverage_matrix


class PlannedSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: str = Field(..., min_length=1)
    purpose: str = Field(..., min_length=1)
    semantic_role: str = "body"
    heading_policy: Literal["render_required", "render_allowed", "internal_only"] = "render_required"


class EvidenceNeed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    need_id: str = Field(..., pattern=r"^EVIDENCE-\d{3,}$")
    description: str = Field(..., min_length=1)
    section_owner: str = Field(..., min_length=1)


class CalculationNeed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    need_id: str = Field(..., pattern=r"^CALC-NEED-\d{3,}$")
    description: str = Field(..., min_length=1)
    section_owner: str = Field(..., min_length=1)


class TransitionEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_section: str = Field(..., min_length=1)
    to_section: str = Field(..., min_length=1)
    handoff: str = Field(..., min_length=1)


class DocumentPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    central_question: str | None = None
    central_claim: str | None = None
    artifact_structure: list[PlannedSection]
    coverage_matrix: dict[str, list[str]] = Field(default_factory=dict)
    terminology: dict[str, str] = Field(default_factory=dict)
    evidence_requirements: list[EvidenceNeed] = Field(default_factory=list)
    calculation_requirements: list[CalculationNeed] = Field(default_factory=list)
    transition_map: list[TransitionEdge] = Field(default_factory=list)
    forbidden_duplications: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_section_references(self) -> "DocumentPlan":
        names = [section.section_id for section in self.artifact_structure]
        if len(names) != len(set(names)):
            raise ValueError("document plan contains duplicate section IDs")
        build_coverage_matrix(self.coverage_matrix, names)
        referenced = {
            *[need.section_owner for need in self.evidence_requirements],
            *[need.section_owner for need in self.calculation_requirements],
            *[edge.from_section for edge in self.transition_map],
            *[edge.to_section for edge in self.transition_map],
        }
        unknown = sorted(referenced - set(names))
        if unknown:
            raise ValueError(f"document plan references unknown section(s): {', '.join(unknown)}")
        return self


def parse_document_plan(raw: str, sections: list[SectionPrompt]) -> tuple[DocumentPlan, bool]:
    """Return a typed plan and whether a legacy compatibility fallback was used."""
    text = raw.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        value = None
    if isinstance(value, dict):
        return DocumentPlan.model_validate(value), False

    # Legacy/custom adapters may still return prose. Keep the public pipeline
    # operational, but never treat that prose as an instruction schema.
    structure = [
        PlannedSection(
            section_id=section.name,
            purpose=section.topic or section.name,
            semantic_role=section.semantic_role,
            heading_policy=section.heading_policy,
        )
        for section in sections
    ]
    return DocumentPlan(artifact_structure=structure), True
