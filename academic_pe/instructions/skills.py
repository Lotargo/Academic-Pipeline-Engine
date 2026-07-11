from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from academic_pe.instructions.models import InstructionRole


class SkillFragment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_id: str = Field(..., pattern=r"^[a-z][a-z0-9_.-]*$")
    description: str = Field(..., min_length=1)
    fragments: dict[InstructionRole, str]


class SkillRegistry:
    """Loads bounded role-specific fragments; agents never receive the full catalog."""

    def __init__(self, skills: list[SkillFragment] | None = None) -> None:
        self._skills = {skill.skill_id: skill for skill in (skills or [])}

    @classmethod
    def from_yaml(cls, path: str | Path = "config/instruction_policies.yaml") -> "SkillRegistry":
        file_path = Path(path)
        if not file_path.exists():
            return cls()
        raw = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
        return cls([SkillFragment.model_validate(item) for item in raw.get("skills", [])])

    def resolve(self, role: InstructionRole | str, skill_ids: list[str]) -> list[str]:
        active_role = InstructionRole(role)
        guidance: list[str] = []
        for skill_id in dict.fromkeys(skill_ids):
            skill = self._skills.get(skill_id)
            if skill is None:
                raise ValueError(f"unknown instruction skill: {skill_id}")
            fragment = skill.fragments.get(active_role)
            if fragment:
                guidance.append(fragment.strip())
        return guidance

    def planner_catalog(self) -> list[dict[str, str]]:
        return [
            {"skill_id": skill.skill_id, "description": skill.description}
            for skill in self._skills.values()
        ]
