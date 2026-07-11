from __future__ import annotations

import json
from collections.abc import Mapping

from academic_pe.core.calculation_audit import CalculationLedger
from academic_pe.core.document_ledger import DocumentLedger


def build_evidence_review_prompt(
    base_prompt: str,
    *,
    document_ledger: DocumentLedger | None,
    calculation_ledger: CalculationLedger | None,
    coverage: Mapping[str, object] | None = None,
) -> str:
    """Build an evidence-only task with traceable registries, not editorial rubrics."""
    ledger = document_ledger or DocumentLedger()
    calculations = calculation_ledger or CalculationLedger()
    evidence_state = {
        "source_cards": [source.model_dump(mode="json") for source in ledger.sources],
        "claim_cards": [claim.model_dump(mode="json") for claim in ledger.claims],
        "calculation_cards": [entry.model_dump(mode="json") for entry in calculations.entries],
        "coverage": dict(coverage or {}),
    }
    return (
        f"{base_prompt}\n\n"
        "You are EvidenceReviewer. Check only factual support and auditability: "
        "ClaimCard-to-SourceCard support, external numbers and dates, assumptions, "
        "CalculationCard expressions/results/units, and contradictions between evidence records and text. "
        "Do not report style, tone, paragraph rhythm, transitions, or wording preferences. "
        "Do not invent missing evidence. Set reviewer_role to 'evidence'.\n\n"
        "[Evidence Review State JSON]\n"
        + json.dumps(evidence_state, ensure_ascii=False, sort_keys=True)
    )
