import pytest

from academic_pe.core.config import SectionPrompt
from academic_pe.instructions import compile_section_brief


def test_section_brief_assigns_owned_and_external_responsibilities():
    brief = compile_section_brief(
        SectionPrompt(name="finance", topic="Financial viability", instruction=""),
        coverage={"viability": ["finance"], "risks": ["risk"], "thesis": ["intro", "finance"]},
        section_names=["intro", "finance", "risk"],
    )

    assert brief.owned_claims == ["viability", "thesis"]
    assert brief.must_not_repeat == ["risks"]


def test_section_brief_rejects_unknown_coverage_owner():
    with pytest.raises(ValueError, match="unknown section"):
        compile_section_brief(
            SectionPrompt(name="finance", topic="Finance", instruction=""),
            coverage={"risks": ["missing"]},
            section_names=["finance"],
        )
