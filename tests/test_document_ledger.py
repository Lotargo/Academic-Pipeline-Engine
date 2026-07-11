import pytest
from pydantic import ValidationError

from academic_pe.core.document_ledger import DocumentLedger


def test_ledger_assigns_stable_source_ids_and_deduplicates_sources():
    ledger = DocumentLedger()
    first = ledger.register_source(
        title="Example Institute. Research report.",
        url="https://example.test/report/",
        source_type="institutional",
        reliability="high",
    )
    duplicate = ledger.register_source(
        title="Example Institute. Research report.",
        url="https://example.test/report",
    )
    second = ledger.register_source(title="Independent study", source_type="paper")

    assert first.source_id == "SRC-001"
    assert duplicate.source_id == "SRC-001"
    assert second.source_id == "SRC-002"
    assert len(ledger.sources) == 2


def test_supported_claim_requires_known_source_and_renders_safe_writer_context():
    ledger = DocumentLedger()
    source = ledger.register_source(title="Official statistic", url="https://example.test/stat")
    claim = ledger.register_claim(
        text="The indicator increased by 10%.",
        source_ids=[source.source_id],
        status="supported",
        section_owner="analysis",
    )

    assert claim.claim_id == "CLAIM-001"
    assert "[SRC-001] Official statistic" in ledger.source_cards_context()
    assert "The indicator increased" not in ledger.source_cards_context()

    with pytest.raises(ValidationError, match="unknown source IDs"):
        ledger.register_claim(
            text="Unsupported mapping.",
            source_ids=["SRC-999"],
            status="supported",
        )


def test_supported_claim_cannot_be_created_without_source():
    with pytest.raises(ValidationError, match="requires at least one source ID"):
        DocumentLedger().register_claim(text="A claim.", status="supported")
