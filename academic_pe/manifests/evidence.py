from __future__ import annotations

from typing import List

from pydantic import BaseModel, ConfigDict, Field


class ManifestSelectionEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    matched_phrases: List[str] = Field(default_factory=list)
    ambiguity_notes: List[str] = Field(default_factory=list)
