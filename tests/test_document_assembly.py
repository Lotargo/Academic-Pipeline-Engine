from academic_pe.core.document_assembly import build_coverage_matrix, assemble_document


def test_assembly_orders_body_before_terminal_and_merges_references():
    sections = [
        {"name": "references", "semantic_role": "reference_section"},
        {"name": "body", "semantic_role": "body"},
        {"name": "bibliography", "semantic_role": "reference_section"},
    ]
    result = assemble_document(
        {
            "references": "[1] Shared source\n[2] First source",
            "body": "Main text.",
            "bibliography": "[1] Shared source\n[3] Second source",
        },
        sections,
    )

    assert list(result.context) == ["body", "references"]
    assert result.context["references"].splitlines() == [
        "[1] Shared source",
        "[2] First source",
        "[3] Second source",
    ]
    assert result.merged_reference_sections == ["bibliography"]


def test_coverage_matrix_accepts_single_owner_and_rejects_unknown_owner():
    matrix = build_coverage_matrix({"coverage": {"central_thesis": "intro"}}, ["intro"])
    assert matrix.coverage == {"central_thesis": ["intro"]}

    try:
        build_coverage_matrix({"coverage": {"risks": ["missing"]}}, ["intro"])
    except ValueError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("unknown coverage owner must be rejected")
