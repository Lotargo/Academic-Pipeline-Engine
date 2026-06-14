from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ArtifactModeOverlay(BaseModel):
    model_config = ConfigDict(extra="forbid")

    add_forbid: List[str] = Field(default_factory=list)
    add_requirements: Dict[str, Any] = Field(default_factory=dict)
    visualization_policy: str = "compatible_only"


class ArtifactManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    version: int = Field(default=1, ge=1)
    artifact_type: str = Field(..., min_length=1)
    description: str = ""
    style: List[str] = Field(default_factory=list)
    audience: str = "general"
    structure: List[str] = Field(default_factory=list)
    forbid: List[str] = Field(default_factory=list)
    requirements: Dict[str, Any] = Field(default_factory=dict)
    content_boundaries: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    modes: Dict[str, ArtifactModeOverlay] = Field(default_factory=dict)

    @field_validator("style", "structure", "forbid", mode="before")
    @classmethod
    def coerce_string_lists(cls, value: Any) -> Any:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return value
