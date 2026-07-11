import json

import pytest
from pydantic import ValidationError

from academic_pe.core.config import SectionPrompt
from academic_pe.instructions import parse_document_plan


def test_document_plan_parses_strict_json_and_coverage():
    raw = json.dumps({
        "central_question": None,
        "central_claim": "The method is suitable.",
        "artifact_structure": [
            {"section_id": "analysis", "purpose": "Assess suitability", "semantic_role": "body", "heading_policy": "render_required"}
        ],
        "coverage_matrix": {"central_claim": ["analysis"]},
        "terminology": {},
        "evidence_requirements": [],
        "calculation_requirements": [],
        "transition_map": [],
        "forbidden_duplications": [],
    })
    plan, legacy = parse_document_plan(raw, [])
    assert not legacy
    assert plan.coverage_matrix == {"central_claim": ["analysis"]}


def test_document_plan_rejects_unknown_owner_and_extra_fields():
    payload = {
        "artifact_structure": [{"section_id": "analysis", "purpose": "Analyze"}],
        "coverage_matrix": {"claim": ["missing"]},
        "unexpected": True,
    }
    with pytest.raises(ValidationError):
        parse_document_plan(json.dumps(payload), [])


def test_document_plan_legacy_prose_becomes_typed_compatibility_plan():
    plan, legacy = parse_document_plan(
        "Legacy prose plan",
        [SectionPrompt(name="body", topic="Body", instruction="Do not copy this raw instruction")],
    )
    assert legacy
    assert plan.artifact_structure[0].section_id == "body"
    assert "raw instruction" not in plan.model_dump_json()
