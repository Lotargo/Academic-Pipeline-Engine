from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from academic_pe.instructions.section_brief import SectionBrief


class InstructionRole(str, Enum):
    PLANNER = "planner"
    RESEARCHER = "researcher"
    WRITER = "writer"
    EVIDENCE_REVIEWER = "evidence_reviewer"
    EDITORIAL_REVIEWER = "editorial_reviewer"
    EXPORTER = "exporter"


class Constraint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    source: str = Field(..., min_length=1)


class ContentReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    kind: str = Field(..., min_length=1)
    value: Any | None = None


class OutputProtocol(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: str = Field(..., min_length=1)
    schema_id: str | None = None


class CompiledInstructionBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: InstructionRole
    objective: str = Field(..., min_length=1)
    hard_constraints: list[Constraint] = Field(default_factory=list)
    content_inputs: list[ContentReference] = Field(default_factory=list)
    section_brief: SectionBrief | None = None
    selected_skill_guidance: list[str] = Field(default_factory=list)
    output_protocol: OutputProtocol


class GatePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gate_ids: list[str] = Field(default_factory=list)
