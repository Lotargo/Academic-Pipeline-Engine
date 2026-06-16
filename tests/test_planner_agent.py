import json

import pytest

from academic_pe.core.config import AgentConfig, SelfCritiqueConfig
from academic_pe.core.llm import LLMProvider
from academic_pe.core.planner_agent import PlannerAgent, PlannerAgentError
from academic_pe.core.templates import RuntimeTemplateSource


class StaticPlannerProvider(LLMProvider):
    def __init__(self, response: str):
        self.response = response
        self.calls = []

    def generate(self, system_prompt, user_prompt, model, temperature, on_delta=None):
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "model": model,
                "temperature": temperature,
            }
        )
        return self.response


class SequencePlannerProvider(LLMProvider):
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.calls = []

    def generate(self, system_prompt, user_prompt, model, temperature, on_delta=None):
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "model": model,
                "temperature": temperature,
            }
        )
        return self.responses[len(self.calls) - 1]


def _planner(response: str) -> PlannerAgent:
    return PlannerAgent(
        AgentConfig(
            role="Planner",
            model="mock",
            temperature=0.0,
            system_prompt="Base planner prompt.",
        ),
        StaticPlannerProvider(response),
    )


def test_planner_agent_parses_runtime_template_and_manifest():
    planner = _planner(
        """
{
  "document_type": "poem",
  "name": "Poem",
  "description": "A temporary poem template.",
  "category": "creative",
  "language_policy": "auto",
  "sections": [
    {
      "name": "poem",
      "title": "Poem",
      "instruction": "Write stanza-oriented poetry.",
      "topic": "Spring field"
    }
  ],
  "prompt_manifest": {
    "planner_role": "Poem planner",
    "writer_role": "Poet",
    "reviewer_role": "Poetry reviewer",
    "writer_task": "Write the poem.",
    "reviewer_task": "Review poetic fit.",
    "style_contract": {
      "tone": "lyrical",
      "structure": "stanzas"
    },
    "review_rubric": {
      "required": ["coherent mood"]
    },
    "output_constraints": {
      "markdown_allowed": true,
      "latex_allowed": false
    }
  }
}
"""
    )

    runtime_template, runtime_manifest = planner.plan(
        topic="Daisies blooming in a field",
        instructions="Make it gentle.",
    )

    assert runtime_template.source == RuntimeTemplateSource.auto
    assert runtime_template.name == "Poem"
    assert runtime_template.sections[0].name == "poem"
    assert runtime_template.metadata["document_type"] == "poem"
    assert runtime_manifest.source == RuntimeTemplateSource.auto
    assert runtime_manifest.prompt_manifest.writer_role == "Poet"
    assert isinstance(planner.llm, StaticPlannerProvider)
    assert "Daisies blooming in a field" in planner.llm.calls[0]["user_prompt"]
    assert "Make it gentle." in planner.llm.calls[0]["user_prompt"]


def test_planner_agent_parses_heading_policy_and_semantic_role():
    planner = _planner(
        """
{
  "document_type": "story_continuation",
  "name": "Story Continuation",
  "description": "A continuation template with private planning beats.",
  "category": "creative",
  "language_policy": "auto",
  "sections": [
    {
      "name": "development",
      "title": "Development",
      "instruction": "Track what the next scene must accomplish.",
      "semantic_role": "narrative_beat",
      "heading_policy": "internal_only"
    },
    {
      "name": "chapter_four",
      "title": "Chapter Four",
      "instruction": "Write the next visible chapter.",
      "semantic_role": "chapter",
      "heading_policy": "user_mandated"
    }
  ],
  "prompt_manifest": {
    "planner_role": "Story planner",
    "writer_role": "Story writer",
    "reviewer_role": "Story reviewer"
  }
}
"""
    )

    runtime_template, _ = planner.plan(
        topic="Continue the story",
        instructions="Keep the chapter title.",
    )

    assert runtime_template.sections[0].semantic_role == "narrative_beat"
    assert runtime_template.sections[0].heading_policy.value == "internal_only"
    assert runtime_template.sections[1].semantic_role == "chapter"
    assert runtime_template.sections[1].heading_policy.value == "user_mandated"


def test_planner_agent_rejects_invalid_json():
    planner = _planner("not json")

    with pytest.raises(PlannerAgentError, match="invalid JSON"):
        planner.parse_plan("not json")


def test_planner_agent_rejects_missing_prompt_manifest():
    planner = _planner("{}")

    with pytest.raises(PlannerAgentError, match="runtime template schema"):
        planner.parse_plan(
            """
{
  "document_type": "article",
  "name": "Article",
  "category": "general",
  "sections": [
    {"name": "article", "title": "Article", "instruction": "Write prose."}
  ]
}
"""
        )


def test_planner_agent_handles_latex_escapes():
    planner = _planner("{}")
    
    # \sigma is an invalid JSON escape character sequence (starts with \s)
    # \theta is technically a valid JSON escape sequence (\t for tab), but in LaTeX context it is a symbol.
    # We expect our parser to safely escape both to \\sigma and \\theta, yielding successful parsing and preserving the LaTeX strings.
    runtime_template, runtime_manifest = planner.parse_plan(
        """
{
  "document_type": "article",
  "name": "Article with LaTeX",
  "category": "academic",
  "language_policy": "auto",
  "sections": [
    {
      "name": "latex_section",
      "title": "LaTeX Section",
      "instruction": "Explain the formula for \\theta and \\sigma and standard newline \\n."
    }
  ],
  "prompt_manifest": {
    "planner_role": "Academic planner",
    "writer_role": "Writer",
    "reviewer_role": "Reviewer",
    "writer_task": "Write prose.",
    "reviewer_task": "Review text.",
    "style_contract": {
      "tone": "formal",
      "structure": "paragraphs"
    },
    "review_rubric": {
      "required": ["accurate LaTeX"]
    },
    "output_constraints": {
      "markdown_allowed": true,
      "latex_allowed": true
    }
  }
}
"""
    )
    
    assert runtime_template.name == "Article with LaTeX"
    assert "formula for \\theta and \\sigma and standard newline" in runtime_template.sections[0].instruction


def test_planner_agent_promotes_all_internal_body_sections_to_draftable():
    planner = _planner("{}")
    runtime_template, _ = planner.parse_plan(
        """
{
  "document_type": "sample_based_report",
  "name": "Sample Based Report",
  "description": "Report following a source sample.",
  "category": "general",
  "language_policy": "auto",
  "sections": [
    {
      "name": "location",
      "title": "Location",
      "instruction": "Describe the location.",
      "semantic_role": "body",
      "heading_policy": "internal_only"
    },
    {
      "name": "technology",
      "title": "Technology",
      "instruction": "Describe the technology.",
      "semantic_role": "body",
      "heading_policy": "internal_only"
    }
  ],
  "prompt_manifest": {
    "writer_role": "Writer",
    "reviewer_role": "Reviewer"
  }
}
"""
    )

    assert [section.heading_policy.value for section in runtime_template.sections] == [
        "render_allowed",
        "render_allowed",
    ]


def test_planner_agent_self_critique_repairs_raw_plan_before_parse():
    raw_plan = """
{
  "document_type": "poem",
  "name": "Generic Plan",
  "description": "A temporary template.",
  "category": "creative",
  "language_policy": "auto",
  "sections": [
    {
      "name": "introduction",
      "title": "Introduction",
      "instruction": "Introduce the topic."
    }
  ],
  "prompt_manifest": {
    "writer_role": "Writer",
    "reviewer_role": "Reviewer",
    "review_rubric": {
      "required": ["coherent"]
    },
    "output_constraints": {
      "markdown_allowed": true,
      "latex_allowed": false
    }
  }
}
"""
    repaired_plan = """
{
  "document_type": "poem",
  "name": "Poem",
  "description": "A temporary poem template.",
  "category": "creative",
  "language_policy": "auto",
  "sections": [
    {
      "name": "poem",
      "title": "Poem",
      "instruction": "Write stanza-oriented poetry."
    }
  ],
  "prompt_manifest": {
    "writer_role": "Poet",
    "reviewer_role": "Poetry reviewer",
    "review_rubric": {
      "required": ["preserve poetic form"]
    },
    "output_constraints": {
      "markdown_allowed": true,
      "latex_allowed": false
    }
  }
}
"""
    provider = SequencePlannerProvider(
        [
            raw_plan,
            json.dumps({"summary": "Restored poem structure.", "output": repaired_plan}),
        ]
    )
    planner = PlannerAgent(
        AgentConfig(
            role="Planner",
            model="mock",
            temperature=0.0,
            system_prompt="Base planner prompt.",
            self_critique=SelfCritiqueConfig(enabled=True),
        ),
        provider,
    )

    runtime_template, runtime_manifest = planner.plan(
        topic="Rain poem",
        instructions="Keep it lyrical.",
    )

    assert runtime_template.name == "Poem"
    assert runtime_template.sections[0].name == "poem"
    assert runtime_manifest.prompt_manifest.writer_role == "Poet"
    assert planner.last_self_critique_summary == "Restored poem structure."
    assert len(provider.calls) == 2
    assert "Planner self-critique" in provider.calls[1]["user_prompt"]
