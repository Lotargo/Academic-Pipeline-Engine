from __future__ import annotations

from enum import Enum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from academic_pe.instructions.models import InstructionRole
from academic_pe.instructions.skills import SkillManifest, SkillRegistry


class GraphNodeType(str, Enum):
    ARTIFACT = "artifact"
    TEMPLATE = "template"
    SKILL = "skill"
    CAPABILITY = "capability"
    AGENT_ROLE = "agent_role"
    GATE = "gate"
    EVIDENCE_SIGNAL = "evidence_signal"


class GraphEdgeType(str, Enum):
    COMPATIBLE_WITH = "compatible_with"
    REQUIRES = "requires"
    PROVIDES = "provides"
    CONFLICTS_WITH = "conflicts_with"
    VERIFIED_BY = "verified_by"
    EXECUTED_BY = "executed_by"
    TRIGGERED_BY = "triggered_by"
    REFINES = "refines"


_EDGE_SHAPES: dict[GraphEdgeType, set[tuple[GraphNodeType, GraphNodeType]]] = {
    GraphEdgeType.COMPATIBLE_WITH: {
        (GraphNodeType.SKILL, GraphNodeType.ARTIFACT),
        (GraphNodeType.TEMPLATE, GraphNodeType.ARTIFACT),
    },
    GraphEdgeType.REQUIRES: {
        (GraphNodeType.SKILL, GraphNodeType.SKILL),
        (GraphNodeType.SKILL, GraphNodeType.CAPABILITY),
    },
    GraphEdgeType.PROVIDES: {(GraphNodeType.SKILL, GraphNodeType.CAPABILITY)},
    GraphEdgeType.CONFLICTS_WITH: {(GraphNodeType.SKILL, GraphNodeType.SKILL)},
    GraphEdgeType.VERIFIED_BY: {(GraphNodeType.SKILL, GraphNodeType.GATE)},
    GraphEdgeType.EXECUTED_BY: {(GraphNodeType.SKILL, GraphNodeType.AGENT_ROLE)},
    GraphEdgeType.TRIGGERED_BY: {(GraphNodeType.SKILL, GraphNodeType.EVIDENCE_SIGNAL)},
    GraphEdgeType.REFINES: {
        (GraphNodeType.SKILL, GraphNodeType.SKILL),
        (GraphNodeType.TEMPLATE, GraphNodeType.ARTIFACT),
    },
}


class SkillGraphEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field(..., pattern=r"^[a-z_]+:[a-z][a-z0-9_.-]*$")
    relation: GraphEdgeType
    target: str = Field(..., pattern=r"^[a-z_]+:[a-z][a-z0-9_.-]*$")

    @field_validator("source", "target")
    @classmethod
    def validate_node_type(cls, value: str) -> str:
        GraphNodeType(value.split(":", 1)[0])
        return value


class SkillPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_skill_ids: list[str] = Field(default_factory=list)
    ordered_skill_ids: list[str] = Field(default_factory=list)
    reasons: dict[str, str] = Field(default_factory=dict)
    unresolved_conflicts: list[str] = Field(default_factory=list)
    gate_ids: list[str] = Field(default_factory=list)
    planner_required: bool = False


class SkillGraph:
    """Validated ontology-lite graph over canonical skill manifests."""

    def __init__(self, manifests: list[SkillManifest], edges: list[SkillGraphEdge] | None = None) -> None:
        self.manifests = {item.skill_id: item for item in manifests}
        if len(self.manifests) != len(manifests):
            raise ValueError("duplicate skill manifest id")
        self.edges = tuple(edges or [])
        self._validate_edges()

    @classmethod
    def from_yaml(
        cls,
        manifest_path: str | Path = "config/instruction_policies.yaml",
        edge_path: str | Path = "config/skill_edges.yaml",
    ) -> "SkillGraph":
        registry = SkillRegistry.from_yaml(manifest_path)
        path = Path(edge_path)
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
        edges = [SkillGraphEdge.model_validate(item) for item in (raw or {}).get("edges", [])]
        return cls(list(registry.manifests), edges)

    def build_plan(
        self,
        skill_ids: list[str],
        *,
        artifact_id: str | None = None,
        role: InstructionRole | str | None = None,
        available_capabilities: set[str] | None = None,
        reasons: dict[str, str] | None = None,
    ) -> SkillPlan:
        selected = list(dict.fromkeys(skill_ids))
        unknown = [skill_id for skill_id in selected if skill_id not in self.manifests]
        if unknown:
            raise ValueError(f"unknown skills: {', '.join(unknown)}")

        active_role = InstructionRole(role) if role is not None else None
        selected_set = set(selected)
        available = set(available_capabilities or ())
        provided = {item for skill_id in selected for item in self.manifests[skill_id].provides}
        unresolved: list[str] = []

        for skill_id in selected:
            manifest = self.manifests[skill_id]
            if artifact_id and manifest.compatible_artifacts and artifact_id not in manifest.compatible_artifacts:
                raise ValueError(f"skill {skill_id} is incompatible with artifact {artifact_id}")
            if active_role and active_role not in manifest.agent_scope:
                raise ValueError(f"skill {skill_id} is not available to role {active_role.value}")
            conflicts = selected_set.intersection(manifest.conflicts_with)
            if conflicts:
                raise ValueError(f"skill {skill_id} conflicts with {', '.join(sorted(conflicts))}")
            for requirement in manifest.requires:
                if requirement not in available and requirement not in provided:
                    unresolved.append(f"{skill_id} requires {requirement}")

        ordered = self._topological_order(selected)
        gates = {
            gate
            for skill_id in selected
            for gate in self.manifests[skill_id].verified_by
        }
        gates.update(
            edge.target.split(":", 1)[1]
            for edge in self.edges
            if edge.relation is GraphEdgeType.VERIFIED_BY
            and edge.source.startswith("skill:")
            and edge.source.split(":", 1)[1] in selected_set
        )
        return SkillPlan(
            selected_skill_ids=selected,
            ordered_skill_ids=ordered,
            reasons={skill_id: (reasons or {}).get(skill_id, "selected by validated skill plan") for skill_id in selected},
            unresolved_conflicts=sorted(set(unresolved)),
            gate_ids=sorted(gates),
            planner_required=bool(unresolved),
        )

    def _validate_edges(self) -> None:
        for edge in self.edges:
            source_type = GraphNodeType(edge.source.split(":", 1)[0])
            target_type = GraphNodeType(edge.target.split(":", 1)[0])
            if (source_type, target_type) not in _EDGE_SHAPES[edge.relation]:
                raise ValueError(
                    f"invalid {edge.relation.value} edge: {source_type.value} -> {target_type.value}"
                )
            for node in (edge.source, edge.target):
                node_type, node_id = node.split(":", 1)
                if node_type == GraphNodeType.SKILL.value and node_id not in self.manifests:
                    raise ValueError(f"graph edge references unknown skill: {node_id}")

    def _topological_order(self, selected: list[str]) -> list[str]:
        selected_set = set(selected)
        dependencies: dict[str, set[str]] = {skill_id: set() for skill_id in selected}
        for edge in self.edges:
            if edge.relation is not GraphEdgeType.REQUIRES:
                continue
            if not edge.source.startswith("skill:") or not edge.target.startswith("skill:"):
                continue
            source = edge.source.split(":", 1)[1]
            target = edge.target.split(":", 1)[1]
            if source in selected_set and target in selected_set:
                dependencies[source].add(target)

        ordered: list[str] = []
        pending = {key: set(value) for key, value in dependencies.items()}
        while pending:
            ready = [skill_id for skill_id in selected if skill_id in pending and not pending[skill_id]]
            if not ready:
                raise ValueError("skill dependency graph contains a cycle")
            for skill_id in ready:
                ordered.append(skill_id)
                pending.pop(skill_id)
                for values in pending.values():
                    values.discard(skill_id)
        return ordered
