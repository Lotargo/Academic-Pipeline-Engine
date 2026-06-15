from __future__ import annotations

from typing import Tuple

from academic_pe.core.document_structure import HeadingPolicy, SemanticRole
from academic_pe.core.config import AppConfig, SectionPrompt
from academic_pe.core.templates import (
    PromptManifest,
    RuntimePromptManifest,
    RuntimeTemplate,
    RuntimeTemplateSource,
    TemplateLanguagePolicy,
    TemplateSection,
)


CUSTOM_CURRENT_TEMPLATE_ID = "custom_current"


def _language_policy(value: object) -> TemplateLanguagePolicy:
    raw_value = getattr(value, "value", value)
    try:
        return TemplateLanguagePolicy(str(raw_value))
    except ValueError:
        return TemplateLanguagePolicy.auto


def section_prompt_to_template_section(section: SectionPrompt) -> TemplateSection:
    return TemplateSection(
        name=section.name,
        title=section.topic or section.name,
        topic=section.topic,
        instruction=section.instruction,
        semantic_role=getattr(section, "semantic_role", None) or SemanticRole.body.value,
        heading_policy=getattr(section, "heading_policy", None) or HeadingPolicy.render_required.value,
    )


def template_section_to_section_prompt(section: TemplateSection) -> SectionPrompt:
    return SectionPrompt(
        name=section.name,
        topic=section.topic or section.title,
        instruction=section.instruction,
        semantic_role=section.semantic_role,
        heading_policy=getattr(section.heading_policy, "value", section.heading_policy),
    )


def custom_current_from_config(config: AppConfig) -> Tuple[RuntimeTemplate, RuntimePromptManifest]:
    writer_role = config.agents.get("writer").role if config.agents.get("writer") else "Writer"
    reviewer_role = config.agents.get("reviewer").role if config.agents.get("reviewer") else "Reviewer"
    language_policy = _language_policy(config.pipeline.language)
    sections = [
        section_prompt_to_template_section(section)
        for section in config.pipeline.sections
    ]

    runtime_template = RuntimeTemplate(
        source=RuntimeTemplateSource.custom,
        source_template_id=CUSTOM_CURRENT_TEMPLATE_ID,
        name="Current Custom Template",
        description="Compatibility runtime template generated from pipeline.sections.",
        category="custom",
        language_policy=language_policy,
        sections=sections,
        metadata={"compatibility_source": "pipeline.sections"},
    )
    runtime_manifest = RuntimePromptManifest(
        source=RuntimeTemplateSource.custom,
        source_template_id=CUSTOM_CURRENT_TEMPLATE_ID,
        prompt_manifest=PromptManifest(
            writer_role=writer_role,
            reviewer_role=reviewer_role,
            style_contract={
                "structure": "pipeline.sections",
                "language_policy": language_policy.value,
            },
            review_rubric={
                "required": [
                    "all configured sections are filled",
                    "content follows the current agent configuration",
                ],
            },
            output_constraints={
                "markdown_allowed": True,
                "latex_allowed": True,
            },
        ),
        metadata={"compatibility_source": "pipeline.sections"},
    )
    return runtime_template, runtime_manifest
