from academic_pe.core.config import AgentConfig, AppConfig, PipelineConfig, SectionPrompt
from academic_pe.core.template_compat import (
    CUSTOM_CURRENT_TEMPLATE_ID,
    custom_current_from_config,
    section_prompt_to_template_section,
)
from academic_pe.core.templates import RuntimeTemplateSource


def test_section_prompt_to_template_section_preserves_current_fields():
    section = SectionPrompt(
        name="theory",
        topic="State Machines",
        instruction="Use H2 and H3 headings.",
        semantic_role="academic_section",
        heading_policy="render_required",
    )

    template_section = section_prompt_to_template_section(section)

    assert template_section.name == "theory"
    assert template_section.title == "State Machines"
    assert template_section.topic == "State Machines"
    assert template_section.instruction == "Use H2 and H3 headings."
    assert template_section.semantic_role == "academic_section"
    assert template_section.heading_policy.value == "render_required"


def test_section_prompt_to_template_section_allows_empty_instruction():
    section = SectionPrompt(name="body", topic="Body", instruction="")

    template_section = section_prompt_to_template_section(section)

    assert template_section.instruction == ""


def test_custom_current_from_config_builds_runtime_snapshots():
    config = AppConfig(
        agents={
            "writer": AgentConfig(
                role="Writer",
                model="mock",
                temperature=0.5,
                system_prompt="writer prompt",
            ),
            "reviewer": AgentConfig(
                role="Reviewer",
                model="mock",
                temperature=0.2,
                system_prompt="reviewer prompt",
            ),
        },
        pipeline=PipelineConfig(
            sections=[
                SectionPrompt(name="theory", topic="Theory", instruction="Explain."),
                SectionPrompt(name="conclusion", topic="Conclusion", instruction="Summarize."),
            ],
        ),
    )

    runtime_template, runtime_manifest = custom_current_from_config(config)

    assert runtime_template.source == RuntimeTemplateSource.custom
    assert runtime_template.source_template_id == CUSTOM_CURRENT_TEMPLATE_ID
    assert [section.name for section in runtime_template.sections] == ["theory", "conclusion"]
    assert runtime_manifest.source == RuntimeTemplateSource.custom
    assert runtime_manifest.source_template_id == CUSTOM_CURRENT_TEMPLATE_ID
    assert runtime_manifest.prompt_manifest.writer_role == "Writer"
    assert runtime_manifest.prompt_manifest.reviewer_role == "Reviewer"
    assert runtime_manifest.prompt_manifest.style_contract["structure"] == "pipeline.sections"
