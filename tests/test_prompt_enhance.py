from academic_pe.server import _build_prompt_enhancement_prompt


def test_prompt_enhancement_preserves_poem_genre():
    prompt = _build_prompt_enhancement_prompt(
        topic="Дама в красном",
        instructions="Сочинить стихотворение, не менее 12 строк, живой образный язык.",
        lang="ru",
    )

    assert "Preserve the artifact as a poem" in prompt
    assert "preserve the artifact type" in prompt
    assert "improve only the creative brief" in prompt
    assert "Do not add new scope, title pages, rubrics, citations" in prompt
    assert "bureaucracy" in prompt
    assert "[Active Artifact Contract]" in prompt
    assert "(artifact creative_poem)" in prompt
    assert "(visualization_required false)" in prompt
    assert "PromptEnhancer adapter rules" in prompt
    assert "candidate-and-critic" in prompt


def test_prompt_enhancement_uses_preserve_first_fallback_for_unknown_artifact():
    prompt = _build_prompt_enhancement_prompt(
        topic="Moonlit field notebook",
        instructions="Keep my odd two-column fragment form and make it clearer.",
        lang="en",
    )

    assert "(artifact unknown_freeform)" in prompt
    assert "preserve-first fallback" in prompt.lower()
    assert "do not invent academic sections or bureaucracy" in prompt
    assert "Selection confidence is low" in prompt
