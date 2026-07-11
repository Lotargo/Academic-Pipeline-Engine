from academic_pe.agent_adapters import contract_guidance_for_agent


def test_reviewer_guidance_base_and_drifts():
    guidance = contract_guidance_for_agent("reviewer")
    assert "Reviewer: check for genre, style, audience, structure" in guidance
    assert "repeated paragraph openings or conclusions" in guidance
    assert "transitions without a real logical relation" in guidance
    assert "unsupported balance phrases" in guidance
    assert "disclaimers" in guidance
    assert "meta-text" in guidance


def test_reviewer_guidance_for_poem():
    guidance = contract_guidance_for_agent("reviewer", "creative_poem")
    assert "Poetic Reviewer checks" in guidance
    assert "Verify that the output is purely creative text without explanations" in guidance
    assert "Reject any clinical summary tone" in guidance


def test_reviewer_guidance_for_story():
    guidance = contract_guidance_for_agent("reviewer", "creative_story")
    assert "Story Reviewer checks" in guidance
    assert "events follow a comprehensible time, cause, place, or viewpoint sequence" in guidance
    assert "Reject sterile summaries" in guidance


def test_reviewer_guidance_for_essay():
    guidance = contract_guidance_for_agent("reviewer", "school_essay")
    assert "School Essay Reviewer checks" in guidance
    assert "Verify that the essay is student-appropriate" in guidance
    assert "sentence complexity, and explanation depth" in guidance


def test_reviewer_guidance_for_readme():
    guidance = contract_guidance_for_agent("reviewer", "technical_readme")
    assert "Technical README Reviewer checks" in guidance
    assert "Verify that all instructions (install, run, config) are realistic" in guidance
    assert "Reject mock placeholders, fabricated functionality" in guidance


def test_reviewer_guidance_for_academic_paper():
    guidance = contract_guidance_for_agent("reviewer", "academic_paper")
    assert "Academic Reviewer checks" in guidance
    assert "Verify logical argumentation, conceptual rigor, and evidence discipline" in guidance
    assert "Reject any generic AI filler phrases" in guidance
