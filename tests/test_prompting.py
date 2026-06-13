from academic_pe.core.config import SectionPrompt
from academic_pe.core.prompting import DEFAULT_DRAFT_TEMPLATE, DEFAULT_PLAN_TEMPLATE, DEFAULT_REVIEW_TEMPLATE, render_template


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
