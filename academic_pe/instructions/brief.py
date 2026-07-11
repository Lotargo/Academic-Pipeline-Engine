from __future__ import annotations

import json
import re

from pydantic import BaseModel, ConfigDict, Field


class NormalizedBrief(BaseModel):
    """Typed user intent. It is data for later compilers, never a Writer prompt."""

    model_config = ConfigDict(extra="forbid")

    topic: str = Field(..., min_length=1)
    artifact_hints: list[str] = Field(default_factory=list)
    explicit_requirements: list[str] = Field(default_factory=list)
    explicit_forbids: list[str] = Field(default_factory=list)
    audience: str | None = None
    tone: str | None = None
    length_hint: str | None = None
    unresolved_ambiguities: list[str] = Field(default_factory=list)

    def legacy_instructions(self) -> str:
        parts = [*self.explicit_requirements]
        parts.extend(f"Do not: {item}" for item in self.explicit_forbids)
        if self.audience:
            parts.append(f"Audience: {self.audience}")
        if self.tone:
            parts.append(f"Tone: {self.tone}")
        if self.length_hint:
            parts.append(f"Length: {self.length_hint}")
        return "\n".join(dict.fromkeys(part.strip() for part in parts if part.strip()))


def parse_normalized_brief(raw: str) -> NormalizedBrief:
    text = (raw or "").strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    return NormalizedBrief.model_validate(json.loads(text))
