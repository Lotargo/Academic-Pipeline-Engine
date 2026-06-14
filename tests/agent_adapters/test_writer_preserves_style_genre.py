from academic_pe.agent_adapters import contract_guidance_for_agent


def test_writer_guidance_for_poem():
    guidance = contract_guidance_for_agent("writer", "creative_poem")
    assert "Lyrical/Poetic writing checks" in guidance
    assert "Focus on natural voice, rhythm, imagery, and emotional coherence" in guidance
    assert "Avoid clinical summary tones" in guidance


def test_writer_guidance_for_story():
    guidance = contract_guidance_for_agent("writer", "creative_story")
    assert "Creative story writing checks" in guidance
    assert "showing instead of telling" in guidance
    assert "narrative voice" in guidance
    assert "Reject sterile summary tones" in guidance


def test_writer_guidance_for_essay():
    guidance = contract_guidance_for_agent("writer", "school_essay")
    assert "School composition writing checks" in guidance
    assert "Maintain an age-appropriate, natural student register" in guidance
    assert "Avoid overly dense research paper structure" in guidance


def test_writer_guidance_for_readme():
    guidance = contract_guidance_for_agent("writer", "technical_readme")
    assert "Technical README writing checks" in guidance
    assert "Write practical, concrete installation, usage, and configuration instructions" in guidance
    assert "Avoid inventing fictitious features" in guidance


def test_writer_guidance_for_academic_paper():
    guidance = contract_guidance_for_agent("writer", "academic_paper")
    assert "Academic writing checks" in guidance
    assert "formal, analytical, and conceptually precise language" in guidance
    assert "Reject generic AI filler phrases" in guidance
