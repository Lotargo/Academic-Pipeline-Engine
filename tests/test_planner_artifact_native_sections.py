import json
import pytest
from academic_pe.core.config import AgentConfig
from academic_pe.core.planner_agent import PlannerAgent, PlannerAgentError
from academic_pe.core.templates import RuntimeTemplateSource
from tests.test_planner_agent import StaticPlannerProvider


def test_planner_parses_poem_sections():
    # Verify that a planned poem structure parses correctly with stanza-oriented sections
    raw_poem_plan = """
{
  "document_type": "poem",
  "name": "Creative Poem Plan",
  "description": "Lyrical poem layout.",
  "category": "creative",
  "language_policy": "auto",
  "sections": [
    {
      "name": "stanza_1",
      "title": "Stanza 1",
      "instruction": "Write the first stanza focusing on imagery."
    },
    {
      "name": "stanza_2",
      "title": "Stanza 2",
      "instruction": "Write the second stanza focusing on conflict and resolution."
    }
  ],
  "prompt_manifest": {
    "writer_role": "Poet",
    "reviewer_role": "Poetry Critic",
    "writer_task": "Write a beautiful lyrical poem.",
    "reviewer_task": "Review imagery and rhythm.",
    "style_contract": {
      "tone": "lyrical",
      "structure": "stanzas"
    },
    "review_rubric": {
      "required": ["imagery", "rhythm"]
    },
    "output_constraints": {
      "markdown_allowed": true,
      "latex_allowed": false
    }
  }
}
"""
    planner = PlannerAgent(
        AgentConfig(role="Planner", model="mock", temperature=0.0, system_prompt=""),
        StaticPlannerProvider(raw_poem_plan)
    )

    template, manifest = planner.plan("Autumn Forest", "Write 2 stanzas.")

    assert template.metadata["document_type"] == "poem"
    assert template.name == "Creative Poem Plan"
    assert len(template.sections) == 2
    assert template.sections[0].name == "stanza_1"
    assert manifest.prompt_manifest.writer_role == "Poet"
    assert manifest.prompt_manifest.style_contract["tone"] == "lyrical"


def test_planner_parses_readme_sections():
    # Verify that a planned README parses correctly with developer-centric headers
    raw_readme_plan = """
{
  "document_type": "readme",
  "name": "Technical README Plan",
  "description": "Developer-centric README layout.",
  "category": "technical",
  "language_policy": "auto",
  "sections": [
    {
      "name": "overview",
      "title": "Overview",
      "instruction": "Explain the goal and features of the library."
    },
    {
      "name": "installation",
      "title": "Installation",
      "instruction": "Provide copy-pasteable install commands."
    },
    {
      "name": "usage",
      "title": "Usage",
      "instruction": "Provide simple code examples."
    }
  ],
  "prompt_manifest": {
    "writer_role": "Technical Writer",
    "reviewer_role": "Developer Reviewer",
    "writer_task": "Write practical README documentation.",
    "reviewer_task": "Check code examples and clear setup.",
    "style_contract": {
      "tone": "concise",
      "structure": "markdown headings"
    },
    "review_rubric": {
      "required": ["reproducibility", "install steps"]
    },
    "output_constraints": {
      "markdown_allowed": true,
      "latex_allowed": false
    }
  }
}
"""
    planner = PlannerAgent(
        AgentConfig(role="Planner", model="mock", temperature=0.0, system_prompt=""),
        StaticPlannerProvider(raw_readme_plan)
    )

    template, manifest = planner.plan("API Project", "Generate README sections.")

    assert template.metadata["document_type"] == "readme"
    assert len(template.sections) == 3
    assert template.sections[1].name == "installation"
    assert manifest.prompt_manifest.writer_role == "Technical Writer"


def test_planner_parses_academic_paper_sections():
    # Verify that a planned academic paper parses correctly with formal sections
    raw_academic_plan = """
{
  "document_type": "academic_paper",
  "name": "Academic Research Plan",
  "description": "Scientific paper layout.",
  "category": "academic",
  "language_policy": "auto",
  "sections": [
    {
      "name": "introduction",
      "title": "Introduction",
      "instruction": "Introduce problem and formulate hypotheses."
    },
    {
      "name": "methodology",
      "title": "Methodology",
      "instruction": "Explain experimental setup and math equations."
    },
    {
      "name": "results",
      "title": "Results & Analysis",
      "instruction": "Detail outcomes with plots and tables."
    }
  ],
  "prompt_manifest": {
    "writer_role": "Researcher",
    "reviewer_role": "Peer Reviewer",
    "writer_task": "Write a rigorous scientific paper.",
    "reviewer_task": "Validate methodologies and claims.",
    "style_contract": {
      "tone": "formal",
      "structure": "sections"
    },
    "review_rubric": {
      "required": ["evidence", "limitations"]
    },
    "output_constraints": {
      "markdown_allowed": true,
      "latex_allowed": true
    }
  }
}
"""
    planner = PlannerAgent(
        AgentConfig(role="Planner", model="mock", temperature=0.0, system_prompt=""),
        StaticPlannerProvider(raw_academic_plan)
    )

    template, manifest = planner.plan("Neural Net Study", "Generate research paper.")

    assert template.metadata["document_type"] == "academic_paper"
    assert len(template.sections) == 3
    assert template.sections[0].name == "introduction"
    assert template.sections[1].name == "methodology"
    assert manifest.prompt_manifest.writer_role == "Researcher"
    assert manifest.prompt_manifest.output_constraints["latex_allowed"] is True
