from academic_pe.core.review_payload import parse_review_payload


def test_structured_review_payload_is_machine_readable():
    payload = parse_review_payload(
        '{"approved": false, "reviewer_role": "evidence", '
        '"summary": "Needs repair", "issues": [{"section": "model", '
        '"line": 8, "severity": "blocker", "code": "NUMERIC_INCONSISTENCY", '
        '"message": "Recalculate NPV."}]}'
    )

    assert payload.approved is False
    assert payload.reviewer_role == "evidence"
    assert payload.issues[0].line == 8
    assert "Recalculate NPV" in payload.reason()


def test_legacy_review_payload_remains_supported():
    approved = parse_review_payload("APPROVED")
    rejected = parse_review_payload("REJECTED\n- [general]: line 3: duplicated conclusion")

    assert approved.approved is True
    assert rejected.approved is False
    assert rejected.issues[0].section == "general"
    assert rejected.issues[0].line == 3
