import pytest

from academic_pe.core.calculation_audit import (
    CalculationEntry,
    CalculationLedger,
    Quantity,
    audit_calculations,
)


def _entry(**overrides):
    data = {
        "calculation_id": "CALC-001",
        "expression": "revenue - costs",
        "inputs": {
            "revenue": Quantity(value=150.0, unit="RUB", source="SRC-001"),
            "costs": Quantity(value=90.0, unit="RUB", source="SRC-002"),
        },
        "expected_result": Quantity(value=60.0, unit="RUB"),
        "section_owner": "financial_model",
    }
    data.update(overrides)
    return CalculationEntry(**data)


def test_audit_recomputes_registered_calculation_with_matching_units():
    result = audit_calculations(CalculationLedger(entries=[_entry()]))

    assert result.passed
    assert result.evaluated["CALC-001"].value == 60.0


def test_audit_rejects_inconsistent_result_and_document_reference():
    result = audit_calculations(
        CalculationLedger(entries=[_entry(expected_result=Quantity(value=61.0, unit="RUB"))]),
        context={"financial_model": "The NPV is recorded as [CALC-001]."},
    )

    assert not result.passed
    assert any("result mismatch" in issue for issue in result.issues)
    assert any("references failed or unknown calculation" in issue for issue in result.issues)


def test_audit_rejects_mixed_units_and_unsafe_expression():
    units_result = audit_calculations(
        CalculationLedger(
            entries=[
                _entry(inputs={"revenue": Quantity(value=150.0, unit="RUB"), "costs": Quantity(value=90.0, unit="m2")})
            ]
        )
    )
    unsafe_result = audit_calculations(
        CalculationLedger(entries=[_entry(expression="__import__('os').system('whoami')")])
    )

    assert not units_result.passed
    assert "compatible units" in units_result.issues[0]
    assert not unsafe_result.passed
    assert "unsupported expression component" in unsafe_result.issues[0]


def test_audit_tracks_dependency_for_sensitivity_scenario():
    base = _entry()
    scenario = CalculationEntry(
        calculation_id="CALC-002",
        expression="calc_001 * multiplier",
        inputs={"multiplier": Quantity(value=0.9, unit="%")},
        expected_result=Quantity(value=54.0, unit="RUB"),
        section_owner="financial_model",
        depends_on=["CALC-001"],
    )

    result = audit_calculations(CalculationLedger(entries=[scenario, base]))

    assert result.passed
    assert set(result.evaluated) == {"CALC-001", "CALC-002"}


def test_audit_rejects_calculation_marker_without_a_registered_ledger_entry():
    result = audit_calculations(None, context={"finance": "The result is [CALC-999]."})

    assert not result.passed
    assert "failed or unknown calculation" in result.issues[0]


def test_audit_compares_marked_text_result_with_registered_calculation():
    result = audit_calculations(
        CalculationLedger(entries=[_entry()]),
        context={"financial_model": "NPV [CALC-001]: 75 RUB."},
    )

    assert not result.passed
    assert "displays 75" in result.issues[0]


def test_audit_accepts_matching_marked_text_result():
    result = audit_calculations(
        CalculationLedger(entries=[_entry()]),
        context={"financial_model": "NPV [CALC-001]: 60 RUB."},
    )

    assert result.passed


def test_calculation_ledger_rejects_duplicate_or_unknown_dependencies():
    entry = _entry(depends_on=["CALC-999"])

    with pytest.raises(ValueError, match="unknown calculations"):
        CalculationLedger(entries=[entry])


def test_calculation_ledger_registers_forward_dependency_batch_and_updates_section_record():
    base = _entry()
    scenario = CalculationEntry(
        calculation_id="CALC-002",
        expression="calc_001 * multiplier",
        inputs={"multiplier": Quantity(value=0.5, unit="%")},
        expected_result=Quantity(value=30.0, unit="RUB"),
        section_owner="financial_model",
        depends_on=["CALC-001"],
    )
    ledger = CalculationLedger()

    ledger.register_many([scenario, base])
    ledger.upsert_many_for_section(
        "financial_model",
        [_entry(expected_result=Quantity(value=60.0, unit="RUB"))],
    )

    assert [entry.calculation_id for entry in ledger.entries] == ["CALC-002", "CALC-001"]
