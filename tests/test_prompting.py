from academic_pe.core.config import SectionPrompt
from academic_pe.core.prompting import (
    DEFAULT_DRAFT_TEMPLATE,
    DEFAULT_PLAN_TEMPLATE,
    DEFAULT_REVIEW_TEMPLATE,
    DEFAULT_REVISION_TEMPLATE,
    render_template,
)


def test_draft_template_uses_section_not_chapter():
    prompt = render_template(
        DEFAULT_DRAFT_TEMPLATE,
        {
            "section": SectionPrompt(name="theory", topic="Finite State Machines", instruction="Use H2/H3."),
            "language_instruction": "Write the entire document in English.",
            "user_topic": "FSM",
            "user_instructions": "",
        },
    )

    assert "Write a section about Finite State Machines." in prompt
    assert "Write a chapter" not in prompt


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
        "section": section,
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
            "section": SectionPrompt(name="poem", topic="Lady in Red", instruction="Write a poem."),
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
