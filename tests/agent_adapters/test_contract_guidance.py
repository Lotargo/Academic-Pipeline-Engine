from academic_pe.agent_adapters import contract_guidance_for_agent


def test_contract_guidance_for_writer_preserves_artifact_voice():
    guidance = contract_guidance_for_agent("writer")

    assert "Writer: produce final content that obeys the contract" in guidance
    assert "Preserve voice, genre, audience level" in guidance
    assert "mode clauses" in guidance
    assert "negative constraints" in guidance
    assert "not false claims about authorship, provenance, or process" in guidance


def test_contract_guidance_for_planner_avoids_generic_academic_structure():
    guidance = contract_guidance_for_agent("planner")

    assert "Planner: choose section structure compatible with the contract" in guidance
    assert "mode clauses" in guidance
    assert "Preserve continuation structure" in guidance
    assert "artifact-native sections" in guidance
    assert "reference_registry" in guidance


def test_contract_guidance_for_reviewer_checks_drift_and_ai_markers():
    guidance = contract_guidance_for_agent("reviewer")

    assert "Reviewer: check for genre, style, audience, structure" in guidance
    assert "forbidden-clause drift" in guidance
    assert "standard_mode and academic_mode clauses" in guidance
    assert "AI/meta markers" in guidance
    assert "artificial smoothness" in guidance
    assert "generic transitions" in guidance
    assert "meaningless balance phrases" in guidance
    assert "disclaimers" in guidance
    assert "not false claims about authorship, provenance, or process" in guidance


def test_contract_guidance_for_researcher_does_not_force_sources():
    guidance = contract_guidance_for_agent("researcher")

    assert "Researcher: search only when the contract or user request requires" in guidance
    assert "Do not force citations" in guidance
    assert "source-free artifacts" in guidance
    assert "reference_registry" in guidance
    assert "new references" in guidance


def test_contract_guidance_for_exporter_preserves_formatting_contract():
    guidance = contract_guidance_for_agent("exporter")

    assert "Exporter: format the artifact according to the contract" in guidance
    assert "do not add title pages or citation sections unless required" in guidance
    assert "artifact-native headings" in guidance


def test_contract_guidance_for_unknown_agent_uses_preserve_intent_fallback():
    guidance = contract_guidance_for_agent("custom_agent")

    assert guidance == "Agent: perform your role without changing the contract's artifact intent."


def test_contract_guidance_for_writer_includes_poem_genre_rules():
    guidance = contract_guidance_for_agent("writer", "creative_poem")

    assert "Lyrical/Poetic writing checks" in guidance
    assert "rhythm, imagery, and emotional coherence" in guidance
    assert "explanations of the poem's meaning" in guidance


def test_contract_guidance_for_reviewer_includes_readme_genre_rules():
    guidance = contract_guidance_for_agent("reviewer", "technical_readme")

    assert "Technical README Reviewer checks" in guidance
    assert "install, run, config" in guidance
    assert "fabricated functionality" in guidance
