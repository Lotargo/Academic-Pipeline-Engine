import pytest

from academic_pe.contracts.models import ArtifactContract
from academic_pe.core.config import SectionPrompt
from academic_pe.instructions import InstructionCompiler
from academic_pe.core.document_ledger import DocumentLedger
from academic_pe.core.calculation_audit import CalculationEntry, CalculationLedger, Quantity


def _contract() -> ArtifactContract:
    return ArtifactContract(
        manifest_id="technical-note",
        artifact="technical_note",
        style=["Use precise terminology."],
        clauses=["Explain assumptions."],
        forbid=["invented sources"],
        structure=["render references last"],
    )


def test_writer_bundle_is_role_scoped_and_coverage_aware():
    bundle = InstructionCompiler().compile(
        "writer",
        artifact_contract=_contract(),
        section=SectionPrompt(name="analysis", topic="Analyze the result", instruction="Use the supplied data."),
        section_names=["intro", "analysis", "conclusion"],
        coverage={"central_claim": ["analysis"], "limitations": ["conclusion"]},
    )

    assert bundle.section_brief is not None
    assert bundle.section_brief.owned_claims == ["central_claim"]
    assert bundle.section_brief.must_not_repeat == ["limitations"]
    assert "Use the supplied data." in bundle.section_brief.writing_constraints
    assert "render references last" not in [item.text for item in bundle.hard_constraints]
    assert bundle.output_protocol.format == "text"


def test_exporter_does_not_receive_writer_style_or_section_brief():
    bundle = InstructionCompiler().compile("exporter", artifact_contract=_contract())

    assert [item.text for item in bundle.hard_constraints] == ["render references last"]
    assert bundle.section_brief is None


def test_writer_requires_section():
    with pytest.raises(ValueError, match="requires a section"):
        InstructionCompiler().compile("writer")


def test_writer_brief_selects_only_section_owned_ledger_inputs():
    ledger = DocumentLedger()
    source = ledger.register_source(title="Study")
    claim = ledger.register_claim(text="Supported result", source_ids=[source.source_id], status="supported", section_owner="analysis")
    ledger.register_claim(text="Other result", status="assumption", section_owner="conclusion")
    calculations = CalculationLedger(entries=[CalculationEntry(
        calculation_id="CALC-001",
        expression="x * 2",
        inputs={"x": Quantity(value=2)},
        expected_result=Quantity(value=4),
        section_owner="analysis",
    )])

    brief = InstructionCompiler().compile(
        "writer",
        section=SectionPrompt(name="analysis", topic="Analysis", instruction=""),
        document_ledger=ledger,
        calculation_ledger=calculations,
    ).section_brief

    assert brief is not None
    assert brief.required_inputs == [claim.claim_id, source.source_id, "CALC-001"]
    assert brief.allowed_sources == [source.source_id]
    assert brief.calculations == ["CALC-001"]
