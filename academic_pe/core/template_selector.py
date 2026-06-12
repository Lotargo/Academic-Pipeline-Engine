from __future__ import annotations

from pathlib import Path
from typing import Optional, Protocol, Tuple

from academic_pe.core.config import AppConfig, TemplateMode
from academic_pe.core.template_compat import custom_current_from_config
from academic_pe.core.template_library import TemplateLibrary
from academic_pe.core.templates import RuntimePromptManifest, RuntimeTemplate


DEFAULT_TEMPLATE_LIBRARY_PATH = Path("config/document_templates.yaml")


class TemplateSelectionError(Exception):
    pass


class AutoTemplatePlanningRequired(TemplateSelectionError):
    pass


class TemplatePlanner(Protocol):
    def plan(
        self,
        topic: str,
        instructions: str = "",
    ) -> Tuple[RuntimeTemplate, RuntimePromptManifest]:
        ...


class TemplateSelector:
    def __init__(
        self,
        library: Optional[TemplateLibrary] = None,
        library_path: str | Path = DEFAULT_TEMPLATE_LIBRARY_PATH,
        planner: Optional[TemplatePlanner] = None,
    ):
        self._library = library
        self._library_path = Path(library_path)
        self._planner = planner

    def select(
        self,
        config: AppConfig,
        topic: str = "",
        instructions: str = "",
    ) -> Tuple[RuntimeTemplate, RuntimePromptManifest]:
        mode = self._template_mode(config)

        if mode == TemplateMode.custom:
            return custom_current_from_config(config)

        if mode == TemplateMode.fixed:
            template_id = config.pipeline.template_id
            if not template_id:
                raise TemplateSelectionError("pipeline.template_id is required when template_mode is fixed.")
            template = self._template_library().get(template_id)
            return (
                RuntimeTemplate.from_document_template(template),
                RuntimePromptManifest.from_document_template(template),
            )

        if mode == TemplateMode.auto:
            if self._planner is None:
                raise AutoTemplatePlanningRequired("template_mode=auto requires PlannerAgent.")
            planner_instructions = instructions
            if getattr(config.pipeline, "academic_mode", False):
                academic_instr = (
                    "Since the document is in Academic Mode, you MUST structure it to include data visualization/plots. "
                    "Ensure that at least one section requires generating a plot/chart (e.g. by writing python-run blocks)."
                )
                if planner_instructions:
                    planner_instructions = f"{planner_instructions}\n\n[Academic Mode Constraint]: {academic_instr}"
                else:
                    planner_instructions = f"[Academic Mode Constraint]: {academic_instr}"
            return self._planner.plan(topic=topic, instructions=planner_instructions)

        raise TemplateSelectionError(f"Unsupported template mode: {mode}")

    def _template_mode(self, config: AppConfig) -> TemplateMode:
        raw_mode = getattr(config.pipeline.template_mode, "value", config.pipeline.template_mode)
        try:
            return TemplateMode(str(raw_mode))
        except ValueError as exc:
            raise TemplateSelectionError(f"Unsupported template mode: {raw_mode}") from exc

    def _template_library(self) -> TemplateLibrary:
        if self._library is None:
            self._library = TemplateLibrary.from_yaml(self._library_path)
        return self._library
