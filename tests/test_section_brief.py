from academic_pe.core.config import SectionPrompt
from academic_pe.instructions import compile_section_brief
from academic_pe.core.prompting import DEFAULT_PATCH_REVISION_TEMPLATE, DEFAULT_REVISION_TEMPLATE, render_template


def test_compile_section_brief_preserves_content_constraints_and_heading_policy():
    brief = compile_section_brief(
        SectionPrompt(
            name="analysis",
            topic="Compare the scenarios",
            instruction="Use CALC-003.\nDo not repeat the methodology.",
            heading_policy="internal_only",
        )
    )

    assert brief.section_id == "analysis"
    assert brief.purpose == "Compare the scenarios"
    assert brief.visible_heading is False
    assert brief.writing_constraints == ["Use CALC-003.", "Do not repeat the methodology."]


def test_compile_section_brief_drops_internal_protocol_lines():
    brief = compile_section_brief(
        SectionPrompt(
            name="body",
            topic="Final prose",
            instruction="[Active Agent Contract]\nUSE_GREP: secret\nWrite one concrete paragraph.",
        )
    )

    assert brief.writing_constraints == ["Write one concrete paragraph."]


def test_writer_revision_templates_use_compiled_brief_not_raw_section_instruction():
    section = SectionPrompt(
        name="body",
        topic="Final prose",
        instruction="[Active Agent Contract]\nWrite one concrete paragraph.",
    )
    brief = compile_section_brief(section).model_dump()
    context = {
        "section_brief": brief,
        "reviewer_reason": "Remove the repeated conclusion.",
        "language_instruction": "Write in English.",
        "user_topic": "Topic",
        "user_instructions": "",
        "continuation_context": "",
        "academic_mode": False,
        "visualization_required": False,
        "output_dir": "exports",
    }

    revision = render_template(DEFAULT_REVISION_TEMPLATE, context)
    patch_revision = render_template(DEFAULT_PATCH_REVISION_TEMPLATE, context)

    assert "Write one concrete paragraph." in revision
    assert "Write one concrete paragraph." in patch_revision
    assert "[Active Agent Contract]" not in revision
    assert "[Active Agent Contract]" not in patch_revision
