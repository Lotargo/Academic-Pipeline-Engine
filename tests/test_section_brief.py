from academic_pe.core.config import SectionPrompt
from academic_pe.instructions import compile_section_brief


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
