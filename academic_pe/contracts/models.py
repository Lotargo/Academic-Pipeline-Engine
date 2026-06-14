from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field


class ArtifactContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest_id: str = Field(..., min_length=1)
    manifest_version: int = Field(default=1, ge=1)
    artifact: str = Field(..., min_length=1)
    language: str = "auto"
    style: List[str] = Field(default_factory=list)
    audience: str = "general"
    mode: str = "new"
    execution_mode: str = "standard"
    structure: List[str] = Field(default_factory=list)
    forbid: List[str] = Field(default_factory=list)
    requirements: Dict[str, Any] = Field(default_factory=dict)
    content_boundaries: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    visualization_required: bool = False
