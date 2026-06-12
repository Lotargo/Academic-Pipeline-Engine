import pytest

from academic_pe.core.config import AgentConfig, AppConfig, PipelineConfig, SectionPrompt, TemplateMode
from academic_pe.core.template_library import TemplateLibrary
from academic_pe.core.template_selector import (
    AutoTemplatePlanningRequired,
    TemplateSelectionError,
    TemplateSelector,
)
from academic_pe.core.templates import (
    DocumentTemplate,
    PromptManifest,
    RuntimePromptManifest,
    RuntimeTemplate,
    RuntimeTemplateSource,
    TemplateSection,
)


def _config(mode: TemplateMode = TemplateMode.custom, template_id: str | None = None) -> AppConfig:
    return AppConfig(
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
            template_mode=mode,
            template_id=template_id,
        ),
    )


def _library() -> TemplateLibrary:
    return TemplateLibrary(
        [
            DocumentTemplate(
                id="technical_note",
                name="Technical Note",
                category="technical",
                sections=[
                    TemplateSection(
                        name="problem",
                        title="Problem",
                        instruction="Define the problem.",
                    ),
                ],
                prompt_manifest=PromptManifest(
                    writer_role="Technical writer",
                    reviewer_role="Technical reviewer",
                ),
            )
        ]
    )


def test_template_selector_uses_custom_current_mode():
    runtime_template, runtime_manifest = TemplateSelector(library=_library()).select(_config())

    assert runtime_template.source == RuntimeTemplateSource.custom
    assert runtime_template.source_template_id == "custom_current"
    assert [section.name for section in runtime_template.sections] == ["theory", "conclusion"]
    assert runtime_manifest.prompt_manifest.writer_role == "Writer"


def test_template_selector_uses_fixed_saved_template():
    runtime_template, runtime_manifest = TemplateSelector(library=_library()).select(
        _config(mode=TemplateMode.fixed, template_id="technical_note")
    )

    assert runtime_template.source == RuntimeTemplateSource.saved
    assert runtime_template.source_template_id == "technical_note"
    assert [section.name for section in runtime_template.sections] == ["problem"]
    assert runtime_manifest.prompt_manifest.writer_role == "Technical writer"


def test_template_selector_requires_template_id_for_fixed_mode():
    with pytest.raises(TemplateSelectionError, match="template_id is required"):
        TemplateSelector(library=_library()).select(_config(mode=TemplateMode.fixed))


def test_template_selector_reports_auto_mode_as_planner_work():
    with pytest.raises(AutoTemplatePlanningRequired, match="requires PlannerAgent"):
        TemplateSelector(library=_library()).select(_config(mode=TemplateMode.auto))


def test_template_selector_uses_planner_for_auto_mode():
    class FakePlanner:
        def __init__(self):
            self.calls = []

        def plan(self, topic: str, instructions: str = ""):
            self.calls.append((topic, instructions))
            template = _library().get("technical_note")
            return (
                RuntimeTemplate.from_document_template(template),
                RuntimePromptManifest.from_document_template(template),
            )

    planner = FakePlanner()

    runtime_template, runtime_manifest = TemplateSelector(
        library=_library(),
        planner=planner,
    ).select(
        _config(mode=TemplateMode.auto),
        topic="Daisies",
        instructions="Use a light tone.",
    )

    assert planner.calls == [("Daisies", "Use a light tone.")]
    assert runtime_template.source_template_id == "technical_note"
    assert runtime_manifest.prompt_manifest.writer_role == "Technical writer"
