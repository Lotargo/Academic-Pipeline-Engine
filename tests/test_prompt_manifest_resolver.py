from academic_pe.core.config import AgentConfig, AppConfig
from academic_pe.core.prompt_manifest_resolver import PromptManifestResolver
from academic_pe.core.templates import PromptManifest, RuntimePromptManifest, RuntimeTemplateSource


def _runtime_manifest() -> RuntimePromptManifest:
    return RuntimePromptManifest(
        source=RuntimeTemplateSource.saved,
        source_template_id="poem",
        prompt_manifest=PromptManifest(
            planner_role="Poem planner",
            writer_role="Poet",
            reviewer_role="Poetry reviewer",
            writer_task="Write stanza-oriented poetry.",
            reviewer_task="Validate poetic fit without academic methodology checks.",
            style_contract={
                "tone": "lyrical",
                "structure": "stanzas",
                "forbidden_devices": ["academic methodology section"],
            },
            review_rubric={
                "required": ["coherent poetic mood"],
                "forbidden": ["demand for formulas"],
            },
            output_constraints={
                "markdown_allowed": True,
                "latex_allowed": False,
                "headings_allowed": False,
            },
        ),
    )


def test_prompt_manifest_resolver_composes_writer_prompt():
    cfg = AgentConfig(
        role="Writer",
        model="mock",
        temperature=0.5,
        system_prompt="Base writer prompt.",
    )

    resolved = PromptManifestResolver().resolve_agent_config("writer", cfg, _runtime_manifest())

    assert resolved.system_prompt.startswith("Base writer prompt.")
    assert "[Active Document Template Manifest]" in resolved.system_prompt
    assert "Role for this document template: Poet" in resolved.system_prompt
    assert "Task for this document template: Write stanza-oriented poetry." in resolved.system_prompt
    assert "structure: stanzas" in resolved.system_prompt
    assert "latex_allowed: false" in resolved.system_prompt


def test_prompt_manifest_resolver_composes_reviewer_prompt():
    cfg = AgentConfig(
        role="Reviewer",
        model="mock",
        temperature=0.2,
        system_prompt="Base reviewer prompt.",
    )

    resolved = PromptManifestResolver().resolve_agent_config("reviewer", cfg, _runtime_manifest())

    assert "Role for this document template: Poetry reviewer" in resolved.system_prompt
    assert "Validate poetic fit without academic methodology checks." in resolved.system_prompt
    assert "demand for formulas" in resolved.system_prompt


def test_prompt_manifest_resolver_does_not_mutate_original_app_config():
    config = AppConfig(
        agents={
            "writer": AgentConfig(
                role="Writer",
                model="mock",
                temperature=0.5,
                system_prompt="Base writer prompt.",
            ),
            "reviewer": AgentConfig(
                role="Reviewer",
                model="mock",
                temperature=0.2,
                system_prompt="Base reviewer prompt.",
            ),
        }
    )

    resolved = PromptManifestResolver().resolve_app_config(config, _runtime_manifest())

    assert config.agents["writer"].system_prompt == "Base writer prompt."
    assert resolved.agents["writer"].system_prompt != config.agents["writer"].system_prompt
    assert "Poet" in resolved.agents["writer"].system_prompt
