from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from academic_pe.instructions.section_brief import SectionBrief
from academic_pe.instructions.style_profile import StyleProfile


INSTRUCTION_BUNDLE_VERSION = "2.0"


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


class PromptBudgetTelemetry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    estimated_tokens: int = Field(ge=0)
    warning_tokens: int = Field(ge=1)
    hard_limit_tokens: int = Field(ge=1)
    status: str = Field(pattern=r"^(ok|warning|exceeded)$")


class CompiledInstructionBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: InstructionRole
    objective: str = Field(..., min_length=1)
    hard_constraints: list[Constraint] = Field(default_factory=list)
    content_inputs: list[ContentReference] = Field(default_factory=list)
    section_brief: SectionBrief | None = None
    style_profile: StyleProfile | None = None
    selected_skill_ids: list[str] = Field(default_factory=list)
    selected_skill_guidance: list[str] = Field(default_factory=list)
    output_protocol: OutputProtocol
    bundle_version: str = INSTRUCTION_BUNDLE_VERSION
    diagnostic_hash: str = Field(default="", pattern=r"^(|[a-f0-9]{64})$")
    prompt_budget: PromptBudgetTelemetry | None = None


class GatePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gate_ids: list[str] = Field(default_factory=list)
