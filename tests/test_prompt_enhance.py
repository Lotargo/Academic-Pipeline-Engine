from academic_pe.server import _build_prompt_enhancement_prompt, _normalize_prompt_enhancement_response


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
    assert "(clauses standard_mode)" in prompt
    assert "[Active Agent Contract]" in prompt
    assert "(agent prompt_enhancer)" in prompt
    assert "(responsibilities clarify_brief reduce_ambiguity preserve_artifact_intent)" in prompt
    assert "(visualization_required false)" in prompt
    assert "PromptEnhancer adapter rules" in prompt
    assert "candidate-and-critic" in prompt
    assert "Treat examples, presets, and candidate labels as illustrative only, never exhaustive" in prompt


def test_prompt_enhancement_uses_preserve_first_fallback_for_unknown_artifact():
    prompt = _build_prompt_enhancement_prompt(
        topic="Moonlit field notebook",
        instructions="Keep my odd two-column fragment form and make it clearer.",
        lang="en",
    )

    assert "(artifact unknown_freeform)" in prompt
    assert "(clauses standard_mode)" in prompt
    assert "preserve-first fallback" in prompt.lower()
    assert "do not invent academic sections or bureaucracy" in prompt
    assert "Selection confidence is low" in prompt


def test_prompt_enhancement_low_confidence_contract_is_advisory():
    prompt = _build_prompt_enhancement_prompt(
        topic="Moonlit field notebook",
        instructions="Keep my odd two-column fragment form and make it clearer.",
        lang="en",
    )

    assert "only as advisory fallback guidance" in prompt
    assert "source of truth when confidence is low" in prompt
    assert "do not block enhancement or return empty fields" in prompt


def test_prompt_enhancement_preserves_non_empty_fields_from_empty_agent_response():
    topic, instructions, fallback_used = _normalize_prompt_enhancement_response(
        '{"topic": "", "instructions": ""}',
        fallback_topic="Original Topic",
        fallback_instructions="Original details.",
    )

    assert topic == "Original Topic"
    assert instructions == "Original details."
    assert fallback_used is True


def test_prompt_enhancement_preserves_fields_from_malformed_agent_response():
    topic, instructions, fallback_used = _normalize_prompt_enhancement_response(
        "not json",
        fallback_topic="Original Topic",
        fallback_instructions="Original details.",
    )

    assert topic == "Original Topic"
    assert instructions == "Original details."
    assert fallback_used is True


def test_prompt_enhancement_passes_academic_mode_as_contract_clause():
    prompt = _build_prompt_enhancement_prompt(
        topic="Lady in Red",
        instructions="Write a poem with 12 lines.",
        lang="en",
        academic_mode=True,
    )

    assert "(artifact creative_poem)" in prompt
    assert "(clauses academic_mode)" in prompt
    assert "(visualization_required false)" in prompt
    assert "academic_mode clause means compatible rigor" in prompt


def test_prompt_enhancer_agent_creation_and_registration():
    from academic_pe.agents.factory import create_agent
    from academic_pe.agents.prompt_enhancer import PromptEnhancerAgent
    from academic_pe.core.config import AgentConfig

    cfg = AgentConfig(
        role="Example Generator",
        model="mock",
        temperature=0.8,
        system_prompt="Enhancer system prompt",
    )
    agent = create_agent("example_generator", cfg, agent_type="prompt_enhancer")
    assert isinstance(agent, PromptEnhancerAgent)


def test_prompt_enhancer_agent_self_critique_success():
    import json
    from academic_pe.agents.prompt_enhancer import PromptEnhancerAgent
    from academic_pe.core.config import AgentConfig, SelfCritiqueConfig
    from academic_pe.core.llm import LLMProvider

    class DoubleGenerateProvider(LLMProvider):
        def __init__(self):
            self.calls = []

        def generate(self, system_prompt, user_prompt, model, temperature, on_delta=None):
            self.calls.append({
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "model": model,
                "temperature": temperature,
            })
            if len(self.calls) == 1:
                return '{"topic": "Unrefined", "instructions": "Unrefined"}'
            else:
                return json.dumps({
                    "summary": "Repaired the prompt.",
                    "output": '{"topic": "Refined Topic", "instructions": "Refined Instructions"}'
                })

    cfg = AgentConfig(
        role="Example Generator",
        model="mock",
        temperature=0.8,
        system_prompt="Enhancer system prompt",
        self_critique=SelfCritiqueConfig(enabled=True, temperature=0.2),
    )
    provider = DoubleGenerateProvider()
    agent = PromptEnhancerAgent(cfg, provider)

    result = agent.process("Raw user prompt")

    assert agent.last_self_critique_summary == "Repaired the prompt."
    assert "Refined Topic" in result
    assert len(provider.calls) == 2
    
    # Verify the critique prompt used prompt_enhancer agent rules
    critique_user_prompt = provider.calls[1]["user_prompt"]
    assert "PromptEnhancer self-critique" in critique_user_prompt
    assert "Agent: prompt_enhancer" in critique_user_prompt


def test_prompt_enhancer_agent_tot_generation_and_selection():
    import json
    from academic_pe.agents.prompt_enhancer import PromptEnhancerAgent
    from academic_pe.core.config import AgentConfig, SelfCritiqueConfig
    from academic_pe.core.llm import LLMProvider

    class TotStaticProvider(LLMProvider):
        def __init__(self):
            self.calls = []

        def generate(self, system_prompt, user_prompt, model, temperature, on_delta=None):
            self.calls.append({
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
            })
            if len(self.calls) == 1:
                return json.dumps({
                    "conservative": {"topic": "Cons Topic", "instructions": "Cons Inst"},
                    "detailed": {"topic": "Detailed Topic", "instructions": "Detailed Inst"},
                    "creative": {"topic": "Creative Topic", "instructions": "Creative Inst"}
                })
            else:
                return json.dumps({
                    "summary": "Selected detailed candidate.",
                    "output": json.dumps({"topic": "Detailed Topic Repaired", "instructions": "Detailed Inst"})
                })

    cfg = AgentConfig(
        role="Example Generator",
        model="mock",
        temperature=0.8,
        system_prompt="Enhancer system prompt",
        self_critique=SelfCritiqueConfig(enabled=True, temperature=0.2),
    )
    provider = TotStaticProvider()
    agent = PromptEnhancerAgent(cfg, provider)
    result = agent.process("Raw topic")

    assert "Detailed Topic Repaired" in result
    assert "Detailed Inst" in result
    assert len(provider.calls) == 2
    assert "INSTRUCTION FOR CANDIDATE GENERATION" in provider.calls[0]["user_prompt"]
    assert "candidate labels as exhaustive" in provider.calls[0]["user_prompt"]


def test_prompt_enhancer_agent_tot_fallback_rejects_obvious_drift():
    import json
    from academic_pe.agents.prompt_enhancer import PromptEnhancerAgent
    from academic_pe.core.config import AgentConfig
    from academic_pe.core.llm import LLMProvider

    class DriftCandidateProvider(LLMProvider):
        def __init__(self):
            self.calls = []

        def generate(self, system_prompt, user_prompt, model, temperature, on_delta=None):
            self.calls.append({
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
            })
            return json.dumps({
                "conservative": {
                    "topic": "Moonlit field notebook",
                    "instructions": "Keep the odd two-column fragment form and clarify details."
                },
                "detailed": {
                    "topic": "Moonlit field notebook research paper",
                    "instructions": "Add a title page, grading rubric, bibliography, and references section."
                },
                "creative": {
                    "topic": "Moonlit field notebook",
                    "instructions": "Use [insert link] and placeholder notes."
                }
            })

    cfg = AgentConfig(
        role="Example Generator",
        model="mock",
        temperature=0.8,
        system_prompt="Enhancer system prompt",
    )
    provider = DriftCandidateProvider()
    agent = PromptEnhancerAgent(cfg, provider)

    result = json.loads(agent.process("Keep my odd two-column fragment form."))

    assert result["topic"] == "Moonlit field notebook"
    assert "two-column fragment form" in result["instructions"]
    assert "title page" not in result["instructions"].lower()
    assert "placeholder" not in result["instructions"].lower()
    assert len(provider.calls) == 1
