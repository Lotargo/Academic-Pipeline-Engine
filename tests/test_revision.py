from copy import deepcopy

import pytest

from academic_pe.core.config import load_config
from academic_pe.core.revision import (
    DocumentRevision,
    RevisionRequest,
    append_revision,
    build_revision_plan,
    execute_patch_revision,
    revision_history,
)


class PatchWriter:
    def __init__(self, response: str):
        self.response = response
        self.calls = []

    def process(self, task, context=None, document_sections=None, **kwargs):
        self.calls.append({"task": task, "context": context, "sections": document_sections})
        return self.response


class ApprovingReviewer(PatchWriter):
    def __init__(self):
        super().__init__("APPROVED")


def _config():
    config = deepcopy(load_config("config/agents.yaml"))
    config.quality_gate.volume.enabled = False
    config.quality_gate.latex.enabled = False
    config.quality_gate.markdown.enabled = False
    config.quality_gate.unicode_hygiene.enabled = False
    config.quality_gate.prompt_leakage.enabled = False
    config.quality_gate.evidence.enabled = False
    config.quality_gate.calculation.enabled = False
    return config


def test_revision_plan_targets_named_section_and_rejects_unknown_target():
    request = RevisionRequest(
        run_id="run_20260712_120000",
        base_revision=1,
        feedback="Correct the conclusion.",
    )
    plan = build_revision_plan(request, {"intro": "Intro", "conclusion": "Old ending"})

    assert plan.affected_sections == ["conclusion"]
    assert [op.type for op in plan.operations] == ["patch_section"]

    with pytest.raises(ValueError, match="unknown affected"):
        build_revision_plan(
            request.model_copy(update={"affected_sections": ["missing"]}),
            {"intro": "Intro"},
        )


def test_patch_revision_changes_only_targeted_section():
    original = {
        "introduction": "This paragraph must remain byte-for-byte unchanged.",
        "conclusion": "Old conclusion.\nSecond old line.",
    }
    writer = PatchWriter("<<<<<<< REPLACE 1-1\nCorrected conclusion.\n>>>>>>>")
    request = RevisionRequest(
        run_id="run_20260712_120000",
        base_revision=1,
        feedback="Please fix the conclusion.",
    )

    result = execute_patch_revision(
        request=request,
        config=_config(),
        writer=writer,
        context=original,
    )

    assert result.changed_sections == ["conclusion"]
    assert result.context["introduction"] == original["introduction"]
    assert result.context["conclusion"] == "Corrected conclusion.\nSecond old line."
    assert len(writer.calls) == 1


def test_revision_reviewer_receives_only_changed_section_text():
    original = {"intro": "Unchanged.", "conclusion": "Old conclusion."}
    writer = PatchWriter("<<<<<<< REPLACE 1-1\nCorrected conclusion.\n>>>>>>>")
    reviewer = ApprovingReviewer()
    request = RevisionRequest(
        run_id="run_20260712_120000",
        base_revision=1,
        feedback="Correct the conclusion.",
    )

    execute_patch_revision(
        request=request,
        config=_config(),
        writer=writer,
        reviewer=reviewer,
        context=original,
    )

    assert len(reviewer.calls) == 1
    assert "=== Section: conclusion ===" in reviewer.calls[0]["context"]
    assert "=== Section: intro ===" not in reviewer.calls[0]["context"]


def test_revision_history_preserves_initial_snapshot_and_new_version():
    metadata = {
        "run_id": "run_20260712_120000",
        "timestamp": "2026-07-12T12:00:00+00:00",
        "context": {"body": "Version one"},
    }
    initial = revision_history(metadata)
    assert initial[0].revision == 1
    assert initial[0].context_snapshot == {"body": "Version one"}

    append_revision(
        metadata,
        DocumentRevision(
            run_id="run_20260712_120000",
            revision=2,
            parent_revision=1,
            trigger="user_feedback",
            status="ready",
            changed_sections=["body"],
            context_snapshot={"body": "Version two"},
        ),
    )
    history = revision_history(metadata)
    assert [item.revision for item in history] == [1, 2]
    assert history[0].context_snapshot == {"body": "Version one"}
    assert history[1].context_snapshot == {"body": "Version two"}
