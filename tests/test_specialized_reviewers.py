import json

import pytest

from academic_pe.core.calculation_audit import CalculationEntry, CalculationLedger, Quantity
from academic_pe.core.document_ledger import DocumentLedger
from academic_pe.review import build_editorial_review_prompt, build_evidence_review_prompt, parse_scoped_review
from academic_pe.core.prompting import DEFAULT_SPECIALIZED_REVIEW_TEMPLATE, render_template


def test_evidence_reviewer_receives_ledgers_but_not_editorial_rubric():
    ledger = DocumentLedger()
    source = ledger.register_source(title="Primary study", url="https://example.test/study")
    ledger.register_claim(text="Measured result", source_ids=[source.source_id], status="supported", section_owner="results")
    calculations = CalculationLedger(entries=[CalculationEntry(
        calculation_id="CALC-001",
        expression="x * 2",
        inputs={"x": Quantity(value=2)},
        expected_result=Quantity(value=4),
        section_owner="results",
    )])

    prompt = build_evidence_review_prompt(
        "Base JSON protocol",
        document_ledger=ledger,
        calculation_ledger=calculations,
        coverage={"measured_result": ["results"]},
    )

    assert "SRC-001" in prompt and "CALC-001" in prompt
    assert "Do not report style, tone" in prompt
    assert "paragraph rhythm" in prompt


def test_editorial_reviewer_receives_coverage_without_evidence_records():
    prompt = build_editorial_review_prompt(
        "Base JSON protocol",
        coverage={"central_claim": ["analysis"]},
        terminology={"API": "application programming interface"},
    )

    assert "central_claim" in prompt and "application programming interface" in prompt
    assert "SourceCard" not in prompt and "CalculationCard" not in prompt
    assert "Do not adjudicate source reliability" in prompt


def test_specialized_json_reviewer_must_report_its_own_role():
    wrong_role = json.dumps({"approved": True, "reviewer_role": "editorial", "issues": [], "summary": ""})
    with pytest.raises(ValueError, match="evidence reviewer"):
        parse_scoped_review(wrong_role, "evidence")

    legacy = parse_scoped_review("APPROVED", "evidence")
    assert legacy.approved and legacy.reviewer_role == "evidence"


def test_specialized_base_protocol_has_no_competing_review_rubric():
    prompt = render_template(
        DEFAULT_SPECIALIZED_REVIEW_TEMPLATE,
        {"language": "en", "review_focus": "", "sections": []},
    )
    assert "unsupported claims" not in prompt
    assert "tone/register drift" not in prompt
    assert '"reviewer_role": "evidence|editorial"' in prompt
