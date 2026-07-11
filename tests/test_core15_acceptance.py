import json
from unittest.mock import patch

from academic_pe.agents.brief_normalizer import BriefNormalizerAgent
from academic_pe.agents.researcher import ResearcherAgent
from academic_pe.agents.writer import WriterAgent
from academic_pe.core.config import AgentConfig, SectionPrompt
from academic_pe.evaluation import run_core15_benchmark
from academic_pe.instructions import InstructionCompiler, extract_style_profile


class StaticProvider:
    def __init__(self, response: str):
        self.response = response
        self.calls = []

    def generate(self, system_prompt, user_prompt, model, temperature, on_delta=None, **kwargs):
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        return self.response


@patch("academic_pe.agents.researcher.run_researcher_pool")
@patch(
    "academic_pe.agents.researcher.load_research_findings",
    return_value="Title: Official report\nURL: https://example.org/report\nRelevant excerpt: measured result",
)
def test_researcher_returns_validated_source_cards(mock_load, mock_pool, tmp_path):
    provider = StaticProvider(json.dumps({
        "notes": "",
        "source_cards": [{
            "source_id": "SRC-001",
            "title": "Official report",
            "url": "https://example.org/report",
            "publication_date": None,
            "source_type": "official_report",
            "reliability": "primary",
            "notes": [],
            "reliability_notes": ["Direct publisher page"],
            "supported_claims": ["measured result"],
            "relevant_excerpt": "measured result",
            "conflicts_with": [],
        }],
        "claims": [{
            "text": "The report contains a measured result.",
            "source_urls": ["https://example.org/report"],
            "status": "supported",
            "section_owner": "analysis",
        }],
    }))
    agent = ResearcherAgent(
        AgentConfig(role="Researcher", provider="zen", model="m", temperature=0, system_prompt="Researcher"),
        provider,
    )

    result = agent.run_research(["query"], str(tmp_path))

    assert "[Source Cards]" in result
    assert agent.last_curation.source_cards[0].source_id == "SRC-001"
    assert "Return one JSON object" in provider.calls[0]["user_prompt"]


def test_brief_normalizer_is_single_pass_and_strict():
    provider = StaticProvider(json.dumps({
        "topic": "API migration note",
        "artifact_hints": ["technical_note"],
        "explicit_requirements": ["Preserve endpoint names"],
        "explicit_forbids": ["invented benchmarks"],
        "audience": "maintainers",
        "tone": "concise",
        "length_hint": None,
        "unresolved_ambiguities": [],
    }))
    agent = BriefNormalizerAgent(
        AgentConfig(role="BriefNormalizer", model="m", temperature=0, system_prompt="Normalize"),
        provider,
    )

    result = json.loads(agent.process("raw task"))

    assert result["explicit_requirements"] == ["Preserve endpoint names"]
    assert len(provider.calls) == 1
    assert "candidate" not in provider.calls[0]["user_prompt"].lower()


def test_brief_normalizer_invalid_model_response_falls_back_to_typed_brief():
    agent = BriefNormalizerAgent(
        AgentConfig(role="BriefNormalizer", model="m", temperature=0, system_prompt="Normalize"),
        StaticProvider("not json"),
    )
    result = json.loads(agent.process("Raw topic: Memo\nRaw instructions: Keep it short"))
    assert result["topic"] == "Memo"
    assert result["explicit_requirements"] == ["Keep it short"]
    assert result["unresolved_ambiguities"] == ["normalizer_model_response_invalid"]


@patch("academic_pe.agents.researcher.load_research_findings", return_value="raw")
@patch("academic_pe.agents.researcher.run_researcher_pool")
def test_mock_research_path_still_produces_source_cards(mock_pool, mock_load, tmp_path):
    mock_pool.return_value = [{
        "query": "q",
        "results": [{
            "title": "Primary page",
            "url": "https://example.org/primary",
            "snippet": "Relevant fact",
            "content": "Relevant fact with bounded context.",
            "extraction_method": "direct",
        }],
    }]
    agent = ResearcherAgent(
        AgentConfig(role="Researcher", provider="mock", model="m", temperature=0, system_prompt="Researcher"),
        StaticProvider("unused"),
    )
    result = agent.run_research(["q"], str(tmp_path))
    assert "SRC-001" in result
    assert agent.last_curation.source_cards[0].url == "https://example.org/primary"


def test_style_profile_is_observable_and_role_scoped():
    sample = "\n\n".join([
        "Я описываю решение коротко и сначала называю ограничение системы.",
        "Затем я показываю конкретный пример и объясняю результат без отдельного вывода.",
        "Терминология API сохраняется, но длинные вводные переходы не используются.",
    ])
    profile = extract_style_profile(sample)
    assert profile is not None and profile.first_person_allowed

    writer = InstructionCompiler().compile(
        "writer",
        section=SectionPrompt(name="body", topic="Body", instruction=""),
        style_profile=profile,
    )
    evidence = InstructionCompiler().compile("evidence_reviewer", style_profile=profile)

    assert writer.style_profile == profile
    assert evidence.style_profile is None
    assert profile.preserve_only_observed_traits


def test_role_specific_skills_budget_version_and_hash_are_deterministic():
    compiler = InstructionCompiler()
    first = compiler.compile(
        "writer",
        section=SectionPrompt(name="body", topic="Body", instruction=""),
        selected_skill_ids=["direct_claims", "source_triangulation"],
    )
    second = compiler.compile(
        "writer",
        section=SectionPrompt(name="body", topic="Body", instruction=""),
        selected_skill_ids=["direct_claims", "source_triangulation"],
    )
    changed = compiler.compile(
        "writer",
        section=SectionPrompt(name="body", topic="Changed", instruction=""),
        selected_skill_ids=["direct_claims"],
    )

    assert first.selected_skill_ids == ["direct_claims", "source_triangulation"]
    assert len(first.selected_skill_guidance) == 1
    assert first.bundle_version == "2.0"
    assert first.diagnostic_hash == second.diagnostic_hash
    assert first.diagnostic_hash != changed.diagnostic_hash
    assert first.prompt_budget.status == "ok"


def test_writer_system_prompt_does_not_advertise_text_grep_protocol():
    provider = StaticProvider("final text")
    agent = WriterAgent(
        AgentConfig(role="Writer", model="m", temperature=0, system_prompt="Writer system"),
        provider,
    )

    assert agent.process("draft", document_sections={"body": "existing"}) == "final text"
    sent = provider.calls[0]["system_prompt"]
    assert "GREP TOOL AVAILABLE" not in sent
    assert "USE_GREP:" not in sent


def test_core15_routing_and_editorial_benchmark_prefers_compiled_scheme():
    report = run_core15_benchmark()
    scores = {item.variant: item for item in report.variants}

    assert report.routing.passed == report.routing.total == 10
    assert report.preferred_variant == "compiled_specialized_reviewers"
    assert scores[report.preferred_variant].editorial_penalty < scores["current_prompts"].editorial_penalty
    assert scores[report.preferred_variant].editorial_score > scores["current_prompts"].editorial_score
    assert all(item.leakage_markers == 0 for name, item in scores.items() if name.startswith("compiled_"))
