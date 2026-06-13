from academic_pe.server import _build_prompt_enhancement_prompt


def test_prompt_enhancement_preserves_poem_genre():
    prompt = _build_prompt_enhancement_prompt(
        topic="Дама в красном",
        instructions="Сочинить стихотворение, не менее 12 строк, живой образный язык.",
        lang="ru",
    )

    assert "If the user asks for a poem" in prompt
    assert "keep that genre" in prompt
    assert "improve only the creative brief" in prompt
    assert "Do not add title pages" in prompt
    assert "grading criteria" in prompt
    assert "document bureaucracy" in prompt
    assert "technical/scientific/academic tasks only" in prompt
