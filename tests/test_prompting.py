from academic_pe.core.config import SectionPrompt
from academic_pe.core.prompting import DEFAULT_DRAFT_TEMPLATE, DEFAULT_REVIEW_TEMPLATE, render_template


def test_draft_template_uses_section_not_chapter():
    prompt = render_template(
        DEFAULT_DRAFT_TEMPLATE,
        {
            "section": SectionPrompt(name="theory", topic="Finite State Machines", instruction="Use H2/H3."),
            "language_instruction": "Write the final section in English.",
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
    assert "at most three" in prompt
