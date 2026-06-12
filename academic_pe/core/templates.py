from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TemplateLanguagePolicy(str, Enum):
    auto = "auto"
    en = "en"
    ru = "ru"


class RuntimeTemplateSource(str, Enum):
    saved = "saved"
    custom = "custom"
    auto = "auto"


class TemplateSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    instruction: str = Field(..., min_length=1)
    topic: Optional[str] = None


class PromptManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    planner_role: Optional[str] = None
    writer_role: str = Field(..., min_length=1)
    reviewer_role: str = Field(..., min_length=1)
    writer_task: Optional[str] = None
    reviewer_task: Optional[str] = None
    style_contract: Dict[str, Any] = Field(default_factory=dict)
    review_rubric: Dict[str, List[str]] = Field(default_factory=dict)
    output_constraints: Dict[str, Any] = Field(default_factory=dict)


class DocumentTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    description: str = ""
    category: str = Field(..., min_length=1)
    language_policy: TemplateLanguagePolicy = TemplateLanguagePolicy.auto
    sections: List[TemplateSection] = Field(..., min_length=1)
    prompt_manifest: PromptManifest
    version: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def section_names_must_be_unique(self) -> "DocumentTemplate":
        names = [section.name for section in self.sections]
        duplicates = {name for name in names if names.count(name) > 1}
        if duplicates:
            raise ValueError(f"Duplicate template section names: {', '.join(sorted(duplicates))}")
        return self


class RuntimeTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: RuntimeTemplateSource
    source_template_id: Optional[str] = None
    source_template_version: Optional[int] = None
    name: str = Field(..., min_length=1)
    description: str = ""
    category: str = Field(..., min_length=1)
    language_policy: TemplateLanguagePolicy = TemplateLanguagePolicy.auto
    sections: List[TemplateSection] = Field(..., min_length=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def section_names_must_be_unique(self) -> "RuntimeTemplate":
        names = [section.name for section in self.sections]
        duplicates = {name for name in names if names.count(name) > 1}
        if duplicates:
            raise ValueError(f"Duplicate runtime section names: {', '.join(sorted(duplicates))}")
        return self

    @classmethod
    def from_document_template(cls, template: DocumentTemplate) -> "RuntimeTemplate":
        return cls(
            source=RuntimeTemplateSource.saved,
            source_template_id=template.id,
            source_template_version=template.version,
            name=template.name,
            description=template.description,
            category=template.category,
            language_policy=template.language_policy,
            sections=template.sections,
        )


class RuntimePromptManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: RuntimeTemplateSource
    source_template_id: Optional[str] = None
    source_template_version: Optional[int] = None
    prompt_manifest: PromptManifest
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_document_template(cls, template: DocumentTemplate) -> "RuntimePromptManifest":
        return cls(
            source=RuntimeTemplateSource.saved,
            source_template_id=template.id,
            source_template_version=template.version,
            prompt_manifest=template.prompt_manifest,
        )
