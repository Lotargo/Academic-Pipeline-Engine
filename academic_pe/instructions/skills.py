from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from academic_pe.instructions.models import InstructionRole


class SkillManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_id: str = Field(..., pattern=r"^[a-z][a-z0-9_.-]*$")
    version: int = Field(default=1, ge=1)
    description: str = Field(..., min_length=1)
    positive_examples: list[str] = Field(default_factory=list)
    negative_examples: list[str] = Field(default_factory=list)
    compatible_artifacts: list[str] = Field(default_factory=list)
    agent_scope: list[InstructionRole] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    requires: list[str] = Field(default_factory=list)
    provides: list[str] = Field(default_factory=list)
    conflicts_with: list[str] = Field(default_factory=list)
    verified_by: list[str] = Field(default_factory=list)
    fragments: dict[InstructionRole, str]

    @model_validator(mode="after")
    def validate_role_scope(self) -> "SkillManifest":
        fragment_roles = set(self.fragments)
        if not self.agent_scope:
            self.agent_scope = list(self.fragments)
        elif not fragment_roles.issubset(set(self.agent_scope)):
            raise ValueError("skill fragments must be included in agent_scope")
        return self


# Compatibility name used by CORE-15 callers.
SkillFragment = SkillManifest


class SkillRegistry:
    """Loads bounded role-specific fragments; agents never receive the full catalog."""

    def __init__(self, skills: list[SkillManifest] | None = None) -> None:
        self._skills = {skill.skill_id: skill for skill in (skills or [])}

    @classmethod
    def from_yaml(cls, path: str | Path = "config/instruction_policies.yaml") -> "SkillRegistry":
        file_path = Path(path)
        if not file_path.exists():
            return cls()
        raw = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
        return cls([SkillManifest.model_validate(item) for item in raw.get("skills", [])])

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

    def planner_catalog(self) -> list[dict[str, object]]:
        return [
            {
                "skill_id": skill.skill_id,
                "version": skill.version,
                "description": skill.description,
                "compatible_artifacts": skill.compatible_artifacts,
                "agent_scope": [role.value for role in skill.agent_scope],
                "requires": skill.requires,
                "provides": skill.provides,
                "conflicts_with": skill.conflicts_with,
            }
            for skill in self._skills.values()
        ]

    @property
    def manifests(self) -> tuple[SkillManifest, ...]:
        return tuple(self._skills.values())

    def get(self, skill_id: str) -> SkillManifest | None:
        return self._skills.get(skill_id)
