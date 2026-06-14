import pytest

from academic_pe.contracts import (
    AgentContract,
    ArtifactContract,
    ContractValidationError,
    compile_agent_contract,
    render_agent_contract_sexpr,
    validate_agent_contract,
)


def _artifact_contract() -> ArtifactContract:
    return ArtifactContract(
        manifest_id="creative_poem",
        manifest_version=1,
        artifact="creative_poem",
        language="ru",
        style=["lyrical", "human"],
        audience="general",
        mode="new",
        execution_mode="standard",
        clauses=["standard_mode"],
        structure=["lines", "stanzas"],
        forbid=["academic_drift", "ai_markers"],
        requirements={
            "theme": 'red "dress"',
            "nested": {"b": 2, "a": "first"},
        },
        visualization_required=False,
    )


def test_compile_agent_contract_adds_writer_adapter_policy():
    agent_contract = compile_agent_contract(_artifact_contract(), "writer")

    assert agent_contract.agent == "writer"
    assert agent_contract.artifact_contract.artifact == "creative_poem"
    assert agent_contract.responsibilities == [
        "produce_final_content",
        "preserve_voice_genre_audience",
        "satisfy_user_constraints",
    ]
    assert agent_contract.checks == ["contract_compliance", "style_fit", "ai_marker_absence"]
    assert agent_contract.forbid == [
        "contract_analysis_output",
        "meta_text",
        "placeholder_text",
        "academic_drift",
    ]

    rendered = render_agent_contract_sexpr(agent_contract)

    assert rendered == render_agent_contract_sexpr(agent_contract)
    assert "(agent writer)" in rendered
    assert "(responsibilities produce_final_content preserve_voice_genre_audience satisfy_user_constraints)" in rendered
    assert "(checks contract_compliance style_fit ai_marker_absence)" in rendered
    assert "(forbid contract_analysis_output meta_text placeholder_text academic_drift)" in rendered
    assert "(artifact_contract" in rendered
    assert "(artifact creative_poem)" in rendered
    assert '(requirement nested ((a "first") (b 2)))' in rendered
    assert '(requirement theme "red \\"dress\\"")' in rendered


def test_compile_agent_contract_covers_manifest_sprint_agents():
    expected = {
        "prompt_enhancer": "clarify_brief",
        "planner": "select_artifact_native_structure",
        "writer": "produce_final_content",
        "reviewer": "quality_gate",
        "researcher": "source_only_when_required",
        "exporter": "format_artifact",
    }

    for agent, responsibility in expected.items():
        agent_contract = compile_agent_contract(_artifact_contract(), agent)

        assert responsibility in agent_contract.responsibilities
        assert agent_contract.checks
        assert agent_contract.forbid
        assert f"(agent {agent})" in render_agent_contract_sexpr(agent_contract)


def test_compile_agent_contract_uses_preserve_intent_fallback_for_unknown_agent():
    agent_contract = compile_agent_contract(_artifact_contract(), "Custom Agent!")

    assert agent_contract.agent == "custom_agent"
    assert "preserve_artifact_intent" in agent_contract.responsibilities
    assert "contract_compliance" in agent_contract.checks
    assert "artifact_change" in agent_contract.forbid


def test_validate_agent_contract_rejects_reserved_adapter_constraint_names():
    agent_contract = AgentContract(
        agent="writer",
        artifact_contract=_artifact_contract(),
        responsibilities=["eval"],
    )

    with pytest.raises(ContractValidationError, match="reserved contract name 'eval'"):
        validate_agent_contract(agent_contract)
