from __future__ import annotations

from typing import Literal

from academic_pe.core.review_payload import StructuredReviewPayload, parse_review_payload


SpecializedRole = Literal["evidence", "editorial"]


def parse_scoped_review(raw: str, expected_role: SpecializedRole) -> StructuredReviewPayload:
    """Validate role identity for JSON while retaining legacy adapter compatibility."""
    payload = parse_review_payload(raw)
    looks_structured = raw.lstrip().startswith("{") or raw.lstrip().startswith("```json")
    if looks_structured and payload.reviewer_role != expected_role:
        raise ValueError(
            f"{expected_role} reviewer returned reviewer_role={payload.reviewer_role!r}"
        )
    return payload.model_copy(update={"reviewer_role": expected_role})
