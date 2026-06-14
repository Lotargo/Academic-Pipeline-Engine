from academic_pe.server import _build_prompt_enhancement_prompt
from academic_pe.agent_adapters.prompt_enhancer import build_prompt_enhancement_prompt


def test_golden_prompt_enhancement_poem():
    prompt = _build_prompt_enhancement_prompt(
        topic="Autumn Forest",
        instructions="Write a 16-line poem with rich autumn colors.",
        lang="en",
    )

    assert "(artifact creative_poem)" in prompt
    assert "(clauses standard_mode)" in prompt
    assert "Preserve the artifact as a poem" in prompt
    assert "Do not add new scope, title pages, rubrics, citations" in prompt
    assert "bureaucracy" in prompt


def test_golden_prompt_enhancement_children_story():
    # Cues like "fairy tale" or "story for children" should resolve to creative_story
    prompt = _build_prompt_enhancement_prompt(
        topic="The Little Bear",
        instructions="Write a simple fairy tale for a 5-year-old child.",
        lang="en",
    )

    assert "(artifact creative_story)" in prompt
    assert "Preserve the artifact as narrative prose" in prompt
    assert "Do not make the output more academic, technical, formal, or adult than requested" in prompt


def test_golden_prompt_enhancement_adult_story():
    # Story with adult constraints
    # Note: adult_content boundary is compiled when content_boundaries is present in manifest
    # Here we can call build_prompt_enhancement_prompt directly with custom continuation_metadata or just let it resolve.
    # Actually, our manifests/resolver.py or configurations load fromconfig/artifact_manifests.yaml.
    # Let's test with a creative_story request and check that the story manifest matches.
    prompt = _build_prompt_enhancement_prompt(
        topic="Adult romance story",
        instructions="An erotic story for mature readers.",
        lang="en",
    )

    assert "(artifact creative_story)" in prompt
    assert "Preserve the artifact as narrative prose" in prompt


def test_golden_prompt_enhancement_school_essay():
    prompt = _build_prompt_enhancement_prompt(
        topic="My summer holidays",
        instructions="A school composition about my summer trips.",
        lang="en",
    )

    assert "(artifact school_essay)" in prompt
    assert "Preserve the school-level assignment" in prompt
    assert "without research overkill" in prompt


def test_golden_prompt_enhancement_readme():
    prompt = _build_prompt_enhancement_prompt(
        topic="API Wrapper project",
        instructions="Create a README with installation instructions and configuration.",
        lang="en",
    )

    assert "(artifact technical_readme)" in prompt
    assert "Preserve the README artifact" in prompt
    assert "without academic prose" in prompt


def test_golden_prompt_enhancement_plan_document():
    prompt = _build_prompt_enhancement_prompt(
        topic="Sprint 2 execution plan",
        instructions="Outline deliverables, tasks, and risks for the next sprint.",
        lang="en",
    )

    assert "(artifact plan_document)" in prompt
    assert "Preserve the plan artifact" in prompt
    assert "without turning it into an essay" in prompt


def test_golden_prompt_enhancement_unknown_artifact():
    prompt = _build_prompt_enhancement_prompt(
        topic="Niche fragment log",
        instructions="Keep it exactly in this custom key-value format and clean up details.",
        lang="en",
    )

    assert "(artifact unknown_freeform)" in prompt
    assert "Use preserve-first fallback behavior" in prompt
    assert "do not invent academic sections or bureaucracy" in prompt


def test_golden_prompt_enhancement_academic_paper():
    prompt = _build_prompt_enhancement_prompt(
        topic="Neural Network optimization",
        instructions="Write an academic research article with methodology and analysis.",
        lang="en",
        academic_mode=True,
    )

    assert "(artifact academic_paper)" in prompt
    assert "(clauses academic_mode)" in prompt
    assert "Preserve the academic artifact" in prompt
    assert "visualization_required true" in prompt.lower()
