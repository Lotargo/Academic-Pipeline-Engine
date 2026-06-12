from __future__ import annotations

from typing import Any, Dict, Optional

import yaml

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
        manifest = runtime_manifest.prompt_manifest
        extra_prompt = self.compose_manifest_prompt(agent_name, manifest)
        if not extra_prompt:
            return config
        return config.model_copy(
            update={"system_prompt": f"{config.system_prompt.rstrip()}\n\n{extra_prompt}"}
        )

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
