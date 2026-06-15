import pytest

from academic_pe.core.continuation import ContinuationIntent
from academic_pe.core.document_state import extract_document_state
from academic_pe.core.merge_operations import (
    MergeOperation,
    MergeOperationType,
    apply_merge_operations,
    build_default_edit_plan,
    compact_merge_patch_metadata,
    parse_merge_operation_payload,
    required_content_roles,
    validate_merge_operation_targets,
)


def _state():
    return extract_document_state(
        {
            "context": {
                "introduction": "Intro text.",
                "analysis": "Old paragraph one.\n\nOld final paragraph.",
                "references": "1. Existing source.",
            },
            "runtime_template": {
                "sections": [
                    {"name": "introduction", "title": "Introduction"},
                    {"name": "analysis", "title": "Analysis"},
                    {
                        "name": "references",
                        "title": "References",
                        "semantic_role": "reference_section",
                    },
                ]
            },
        }
    )


def test_default_continue_plan_inserts_before_terminal_sections():
    plan = build_default_edit_plan(
        ContinuationIntent.continue_append,
        ["references"],
    )

    assert [operation.op for operation in plan.operations] == [
        MergeOperationType.preserve,
        MergeOperationType.insert_before,
        MergeOperationType.move_terminal_sections_to_end,
    ]
    assert plan.operations[1].target == "references"
    assert plan.operations[1].content_role == "continuation"


def test_apply_insert_before_keeps_references_terminal():
    patch = apply_merge_operations(
        _state(),
        [
            {"op": "preserve", "target": "existing_body"},
            {
                "op": "insert_before",
                "target": "references",
                "content_role": "continuation",
            },
            {"op": "move_terminal_sections_to_end"},
        ],
        {"continuation": "New analysis paragraph."},
    )

    assert list(patch.assembled_context.keys()) == [
        "introduction",
        "analysis",
        "continuation",
        "references",
    ]
    assert patch.assembled_context["continuation"] == "New analysis paragraph."
    assert patch.assembled_context["references"] == "1. Existing source."


def test_apply_replace_tail_smooths_bridge():
    patch = apply_merge_operations(
        _state(),
        [
            {
                "op": "replace_tail",
                "target": "analysis",
                "paragraphs": 1,
                "content_role": "smooth_bridge",
            },
            {
                "op": "append_after",
                "target": "analysis",
                "content_role": "continuation",
            },
        ],
        {
            "smooth_bridge": "Bridge paragraph.",
            "continuation": "Continuation paragraph.",
        },
    )

    assert patch.assembled_context["analysis"] == (
        "Old paragraph one.\n\nBridge paragraph.\n\nContinuation paragraph."
    )
    assert patch.replaced_ranges["analysis"] == "tail:1"
    assert patch.inserted_content["analysis"] == "Continuation paragraph."


def test_update_references_deduplicates_and_records_terminal():
    patch = apply_merge_operations(
        _state(),
        [
            {
                "op": "update_references",
                "target": "references",
                "content": "1. Existing source.\n2. New source.",
                "mode": "dedupe_and_merge",
            }
        ],
    )

    assert patch.assembled_context["references"] == "1. Existing source.\n2. New source."
    assert patch.updated_references == ["references"]


def test_update_references_deduplicates_across_marker_styles_and_skips_heading():
    patch = apply_merge_operations(
        _state(),
        [
            {
                "op": "update_references",
                "target": "references",
                "content": "## References\n[1] Existing source.\n- New source.",
                "mode": "dedupe_and_merge",
            }
        ],
    )

    assert patch.assembled_context["references"] == "1. Existing source.\n- New source."


def test_merge_operation_validates_required_shape():
    with pytest.raises(ValueError, match="replace_tail requires paragraphs"):
        MergeOperation(op="replace_tail", target="analysis")


def test_parse_merge_operation_payload_from_fenced_json():
    payload = parse_merge_operation_payload(
        """```json
{
  "operation_outputs": {
    "continuation": "New body."
  },
  "reviewer_notes": ["ok"]
}
```"""
    )

    assert payload.operation_outputs == {"continuation": "New body."}
    assert payload.reviewer_notes == ["ok"]


def test_required_content_roles_ignores_inline_content():
    roles = required_content_roles(
        [
            {"op": "insert_before", "target": "references", "content_role": "continuation"},
            {"op": "update_references", "target": "references", "content_role": "references", "content": "Inline"},
        ]
    )

    assert roles == ["continuation"]


def test_compact_merge_patch_metadata_omits_full_assembled_context():
    patch = apply_merge_operations(
        _state(),
        [{"op": "append_after", "target": "analysis", "content_role": "continuation"}],
        {"continuation": "New analysis."},
    )

    metadata = compact_merge_patch_metadata(patch)

    assert metadata["assembled_section_order"] == ["introduction", "analysis", "references"]
    assert "assembled_context" not in metadata


def test_validate_merge_operation_targets_accepts_default_plan():
    state = _state()
    plan = build_default_edit_plan(
        ContinuationIntent.continue_append,
        state.terminal_sections,
    )

    assert validate_merge_operation_targets(state, plan.operations) == []


def test_validate_merge_operation_targets_rejects_unknown_insert_anchor():
    issues = validate_merge_operation_targets(
        _state(),
        [{"op": "insert_before", "target": "missing_anchor", "content_role": "continuation"}],
    )

    assert issues == [
        "insert_before target 'missing_anchor' does not resolve to an existing section"
    ]


def test_validate_merge_operation_targets_rejects_appending_after_terminal_section():
    issues = validate_merge_operation_targets(
        _state(),
        [{"op": "append_after", "target": "references", "content_role": "continuation"}],
    )

    assert issues == [
        "append_after target 'references' resolves to terminal section 'references'"
    ]
