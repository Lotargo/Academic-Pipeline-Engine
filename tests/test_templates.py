import pytest
from pydantic import ValidationError

from academic_pe.core.templates import (
    DocumentTemplate,
    HeadingPolicy,
    PromptManifest,
    RuntimePromptManifest,
    RuntimeTemplate,
    RuntimeTemplateSource,
    TemplateSection,
)


def _manifest() -> PromptManifest:
    return PromptManifest(
        writer_role="General document writer",
        reviewer_role="General document reviewer",
        style_contract={"tone": "neutral"},
        review_rubric={"required": ["coherent flow"]},
        output_constraints={"markdown_allowed": True},
    )


def _template() -> DocumentTemplate:
    return DocumentTemplate(
        id="freeform_article",
        name="Freeform Article",
        description="Readable prose without heavy academic structure.",
        category="general",
        sections=[
            TemplateSection(
                name="body",
                title="Body",
                instruction="Write coherent article prose.",
            ),
        ],
        prompt_manifest=_manifest(),
    )


def test_document_template_requires_prompt_manifest():
    with pytest.raises(ValidationError):
        DocumentTemplate.model_validate({
            "id": "invalid",
            "name": "Invalid",
            "category": "general",
            "sections": [
                {
                    "name": "body",
                    "title": "Body",
                    "instruction": "Write the document body.",
                }
            ],
        })


def test_document_template_rejects_duplicate_section_names():
    with pytest.raises(ValidationError, match="Duplicate template section names"):
        DocumentTemplate(
            id="duplicate_sections",
            name="Duplicate Sections",
            category="general",
            sections=[
                TemplateSection(name="body", title="Body", instruction="First."),
                TemplateSection(name="body", title="Body Again", instruction="Second."),
            ],
            prompt_manifest=_manifest(),
        )


def test_runtime_snapshots_from_document_template():
    template = _template()

    runtime_template = RuntimeTemplate.from_document_template(template)
    runtime_manifest = RuntimePromptManifest.from_document_template(template)

    assert runtime_template.source == RuntimeTemplateSource.saved
    assert runtime_template.source_template_id == "freeform_article"
    assert runtime_template.sections[0].name == "body"
    assert runtime_manifest.source == RuntimeTemplateSource.saved
    assert runtime_manifest.prompt_manifest.writer_role == "General document writer"


def test_prompt_manifest_coerces_string_rubric():
    manifest = PromptManifest(
        writer_role="Writer",
        reviewer_role="Reviewer",
        review_rubric={
            "required": "coherent flow",
            "forbidden": ["broken link"],
            "custom_item": "some string values"
        }
    )
    assert manifest.review_rubric["required"] == ["coherent flow"]
    assert manifest.review_rubric["forbidden"] == ["broken link"]
    assert manifest.review_rubric["custom_item"] == ["some string values"]


def test_template_section_accepts_heading_policy_and_semantic_role():
    section = TemplateSection(
        name="development",
        title="Development",
        instruction="Track the narrative beat internally.",
        semantic_role="narrative_beat",
        heading_policy="internal_only",
    )

    assert section.semantic_role == "narrative_beat"
    assert section.heading_policy == HeadingPolicy.internal_only
