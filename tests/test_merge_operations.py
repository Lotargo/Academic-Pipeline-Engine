import pytest

from academic_pe.core.continuation import ContinuationIntent
from academic_pe.core.document_state import extract_document_state
from academic_pe.core.merge_operations import (
    MergeOperation,
    MergeOperationType,
    apply_merge_operations,
    build_default_edit_plan,
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


def test_merge_operation_validates_required_shape():
    with pytest.raises(ValueError, match="replace_tail requires paragraphs"):
        MergeOperation(op="replace_tail", target="analysis")
