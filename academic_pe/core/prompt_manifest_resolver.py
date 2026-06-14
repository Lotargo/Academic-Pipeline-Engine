from __future__ import annotations

from typing import Any, Dict, Optional

import yaml
from pydantic import ValidationError

from academic_pe.agent_adapters import contract_guidance_for_agent
from academic_pe.contracts import ArtifactContract, compile_agent_contract, render_agent_contract_sexpr
from academic_pe.core.config import AgentConfig, AppConfig
from academic_pe.core.templates import PromptManifest, RuntimePromptManifest


class PromptManifestResolver:
    def resolve_app_config(
        self,
        config: AppConfig,
        runtime_manifest: RuntimePromptManifest,
    ) -> AppConfig:
        resolved_config = config.model_copy(deep=True)
        resolved_agents: Dict[str, AgentConfig] = {}
        for name, agent_config in resolved_config.agents.items():
            resolved_agents[name] = self.resolve_agent_config(
                name,
                agent_config,
                runtime_manifest,
            )
        resolved_config.agents = resolved_agents
        return resolved_config

    def resolve_agent_config(
        self,
        agent_name: str,
        config: AgentConfig,
        runtime_manifest: RuntimePromptManifest,
    ) -> AgentConfig:
        extra_prompt = self.compose_runtime_manifest_prompt(agent_name, runtime_manifest)
        if not extra_prompt:
            return config
        return config.model_copy(
            update={"system_prompt": f"{config.system_prompt.rstrip()}\n\n{extra_prompt}"}
        )

    def compose_runtime_manifest_prompt(
        self,
        agent_name: str,
        runtime_manifest: RuntimePromptManifest,
    ) -> str:
        sections: list[str] = []

        template_prompt = self.compose_manifest_prompt(agent_name, runtime_manifest.prompt_manifest)
        if template_prompt:
            sections.append(template_prompt)

        artifact_contract = self._artifact_contract_prompt(agent_name, runtime_manifest)
        if artifact_contract:
            sections.append(artifact_contract)

        agent_contract = self._agent_contract_prompt(agent_name, runtime_manifest)
        if agent_contract:
            sections.append(agent_contract)

        return "\n\n".join(sections)

    def compose_manifest_prompt(self, agent_name: str, manifest: PromptManifest) -> str:
        sections: list[str] = []

        role = self._role_for_agent(agent_name, manifest)
        if role:
            sections.append(f"Role for this document template: {role}")

        task = self._task_for_agent(agent_name, manifest)
        if task:
            sections.append(f"Task for this document template: {task}")

        if manifest.style_contract:
            sections.append("[Template Style Contract]\n" + self._format_mapping(manifest.style_contract))

        if manifest.review_rubric:
            sections.append("[Template Review Rubric]\n" + self._format_mapping(manifest.review_rubric))

        if manifest.output_constraints:
            sections.append("[Template Output Constraints]\n" + self._format_mapping(manifest.output_constraints))

        if not sections:
            return ""

        return "[Active Document Template Manifest]\n" + "\n\n".join(sections)

    def _artifact_contract_prompt(
        self,
        agent_name: str,
        runtime_manifest: RuntimePromptManifest,
    ) -> str:
        metadata = runtime_manifest.metadata or {}
        contract_sexpr = metadata.get("contract_sexpr")
        if not isinstance(contract_sexpr, str) or not contract_sexpr.strip():
            return ""

        resolved_manifest = metadata.get("resolved_manifest")
        artifact_id = resolved_manifest.get("id") if isinstance(resolved_manifest, dict) else None

        guidance = contract_guidance_for_agent(agent_name, artifact_id)
        return (
            "[Active Artifact Contract]\n"
            "Use this compact contract as the highest-priority artifact intent. "
            "Preserve the requested artifact type, style, audience, structure, mode, and forbid clauses unless the current user request explicitly changes them.\n"
            f"{guidance}\n"
            f"{contract_sexpr.strip()}"
        )

    def _agent_contract_prompt(
        self,
        agent_name: str,
        runtime_manifest: RuntimePromptManifest,
    ) -> str:
        metadata = runtime_manifest.metadata or {}
        contract_data = metadata.get("resolved_contract")
        if not isinstance(contract_data, dict):
            return ""

        try:
            artifact_contract = ArtifactContract.model_validate(contract_data)
            agent_contract = compile_agent_contract(artifact_contract, agent_name)
        except (TypeError, ValueError, ValidationError):
            return ""

        return (
            "[Active Agent Contract]\n"
            "This is the adapter-specific contract compiled from the artifact contract and the current agent role.\n"
            f"{render_agent_contract_sexpr(agent_contract)}"
        )

    def _role_for_agent(self, agent_name: str, manifest: PromptManifest) -> Optional[str]:
        if agent_name == "writer":
            return manifest.writer_role
        if agent_name == "reviewer":
            return manifest.reviewer_role
        if agent_name == "planner":
            return manifest.planner_role
        return None

    def _task_for_agent(self, agent_name: str, manifest: PromptManifest) -> Optional[str]:
        if agent_name == "writer":
            return manifest.writer_task
        if agent_name == "reviewer":
            return manifest.reviewer_task
        return None

    def _format_mapping(self, value: Dict[str, Any]) -> str:
        return yaml.safe_dump(
            value,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        ).strip()
