from academic_pe.core.config import SectionPrompt
from academic_pe.instructions import compile_section_brief
from academic_pe.core.prompting import (
    DEFAULT_DRAFT_TEMPLATE,
    DEFAULT_MERGE_OPERATION_TEMPLATE,
    DEFAULT_PLAN_TEMPLATE,
    DEFAULT_REVIEW_TEMPLATE,
    DEFAULT_REVISION_TEMPLATE,
    render_template,
)


def test_draft_template_uses_section_not_chapter():
    prompt = render_template(
        DEFAULT_DRAFT_TEMPLATE,
        {
            "section_brief": compile_section_brief(SectionPrompt(name="theory", topic="Finite State Machines", instruction="Use H2/H3.")).model_dump(),
            "language_instruction": "Write the entire document in English.",
            "user_topic": "FSM",
            "user_instructions": "",
        },
    )

    assert "Purpose: Finite State Machines." in prompt
    assert "Write a chapter" not in prompt


def test_draft_template_does_not_accept_raw_research_or_reference_context():
    prompt = render_template(
        DEFAULT_DRAFT_TEMPLATE,
        {
            "section_brief": compile_section_brief(SectionPrompt(name="body", topic="Draft section", instruction="Write clean prose.")).model_dump(),
            "language_instruction": "Write the entire document in English.",
            "user_topic": "Topic",
            "user_instructions": "",
            "reference_materials": [
                {"filename": "source.md", "content": "RAW_REFERENCE_CONTENT_SHOULD_NOT_APPEAR"},
            ],
            "search_findings": "RAW_SEARCH_FINDINGS_SHOULD_NOT_APPEAR",
        },
    )

    assert "RAW_REFERENCE_CONTENT_SHOULD_NOT_APPEAR" not in prompt
    assert "RAW_SEARCH_FINDINGS_SHOULD_NOT_APPEAR" not in prompt
    assert "Research drafting rules" not in prompt


def test_review_template_accepts_focus_and_limits_issues():
    prompt = render_template(
        DEFAULT_REVIEW_TEMPLATE,
        {
            "language": "en",
            "review_focus": "Fix inconsistent notation.",
        },
    )

    assert "Review focus from the previous attempt: Fix inconsistent notation." in prompt
    assert "group the issues by the section" in prompt


def test_generic_templates_are_artifact_neutral_without_academic_mode():
    section = SectionPrompt(name="scene", topic="Summer field", instruction="Write a lyrical scene.")
    base_context = {
        "section_brief": compile_section_brief(section).model_dump(),
        "language_instruction": "Write the entire document in English.",
        "user_topic": "Summer field",
        "user_instructions": "Write a lyrical scene.",
        "academic_mode": False,
        "visualization_required": False,
    }

    draft_prompt = render_template(DEFAULT_DRAFT_TEMPLATE, base_context)
    plan_prompt = render_template(
        DEFAULT_PLAN_TEMPLATE,
        {
            "sections": [section],
            "language_instruction": "Write the entire document in English.",
            "user_topic": "Summer field",
            "user_instructions": "Write a lyrical scene.",
            "academic_mode": False,
            "visualization_required": False,
        },
    )
    revision_prompt = render_template(
        DEFAULT_REVISION_TEMPLATE,
        {
            **base_context,
            "reviewer_reason": "Tighten one sentence.",
        },
    )
    review_prompt = render_template(
        DEFAULT_REVIEW_TEMPLATE,
        {
            "language": "en",
            "review_focus": "",
            "academic_mode": False,
            "visualization_required": False,
        },
    )

    combined = "\n".join([draft_prompt, plan_prompt, revision_prompt, review_prompt])

    assert "requested tone/register" in draft_prompt
    assert "requested artifact" in plan_prompt
    assert "active artifact contract and user request" in review_prompt
    assert "academic impersonal tone" not in combined
    assert "academic document" not in combined
    assert "material academic quality" not in combined
    assert "academic tone" not in combined


def test_academic_mode_does_not_force_visualization_by_default():
    prompt = render_template(
        DEFAULT_DRAFT_TEMPLATE,
        {
            "section_brief": compile_section_brief(SectionPrompt(name="poem", topic="Lady in Red", instruction="Write a poem.")).model_dump(),
            "language_instruction": "Write the entire document in English.",
            "user_topic": "Lady in Red",
            "user_instructions": "Write a poem.",
            "academic_mode": True,
            "visualization_required": False,
        },
    )

    assert "Academic Mode: strengthen conceptual rigor" in prompt
    assert "Visualization Requirement" not in prompt
    assert "python-run" not in prompt
    assert "MUST support your theoretical or computational claims with data visualizations" not in prompt


def test_visualization_requirement_is_explicit_contract_clause():
    prompt = render_template(
        DEFAULT_PLAN_TEMPLATE,
        {
            "sections": [
                SectionPrompt(name="analysis", topic="Measurements", instruction="Analyze data."),
            ],
            "language_instruction": "Write the entire document in English.",
            "user_topic": "Measurements",
            "user_instructions": "Use measured data.",
            "academic_mode": True,
            "visualization_required": True,
        },
    )

    assert "[Visualization Requirement]" in prompt
    assert "python-run" in prompt


def test_merge_operation_template_uses_reference_registry_policy():
    prompt = render_template(
        DEFAULT_MERGE_OPERATION_TEMPLATE,
        {
            "language_instruction": "Write the entire document in English.",
            "language": "en",
            "user_topic": "Continue report",
            "user_instructions": "Add sources.",
            "edit_plan_json": '{"operations": [{"op": "update_references", "content_role": "references"}]}',
            "document_state_json": '{"reference_registry": [{"raw_text": "1. Existing source."}]}',
        },
    )

    assert "Use `reference_registry` from Document State as the source registry" in prompt
    assert "write only bare reference entries to merge" in prompt
    assert "New references" in prompt
