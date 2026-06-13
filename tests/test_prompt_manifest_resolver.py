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


def _runtime_manifest_with_contract() -> RuntimePromptManifest:
    manifest = _runtime_manifest()
    return manifest.model_copy(
        update={
            "metadata": {
                "contract_sexpr": """(document
  (manifest creative_poem 1)
  (artifact creative_poem)
  (language ru)
  (style lyrical human)
  (audience general)
  (mode new)
  (execution_mode academic)
  (forbid academic_drift forced_visualization research_paper_structure)
  (visualization_required false)
)""",
                "resolved_contract": {
                    "artifact": "creative_poem",
                    "visualization_required": False,
                },
            }
        }
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


def test_prompt_manifest_resolver_adds_artifact_contract_to_writer_prompt():
    cfg = AgentConfig(
        role="Writer",
        model="mock",
        temperature=0.5,
        system_prompt="Base writer prompt.",
    )

    resolved = PromptManifestResolver().resolve_agent_config(
        "writer",
        cfg,
        _runtime_manifest_with_contract(),
    )

    assert "[Active Artifact Contract]" in resolved.system_prompt
    assert "Writer: produce final content that obeys the contract" in resolved.system_prompt
    assert "(artifact creative_poem)" in resolved.system_prompt
    assert "(forbid academic_drift forced_visualization research_paper_structure)" in resolved.system_prompt
    assert "(visualization_required false)" in resolved.system_prompt


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


def test_prompt_manifest_resolver_adds_reviewer_drift_guidance():
    cfg = AgentConfig(
        role="Reviewer",
        model="mock",
        temperature=0.2,
        system_prompt="Base reviewer prompt.",
    )

    resolved = PromptManifestResolver().resolve_agent_config(
        "reviewer",
        cfg,
        _runtime_manifest_with_contract(),
    )

    assert "Reviewer: check for genre, style, audience, structure, prompt, and forbidden-clause drift" in resolved.system_prompt
    assert "(artifact creative_poem)" in resolved.system_prompt


def test_prompt_manifest_resolver_adds_planner_structure_guidance():
    cfg = AgentConfig(
        role="Planner",
        model="mock",
        temperature=0.2,
        system_prompt="Base planner prompt.",
    )

    resolved = PromptManifestResolver().resolve_agent_config(
        "planner",
        cfg,
        _runtime_manifest_with_contract(),
    )

    assert "Planner: choose section structure compatible with the contract" in resolved.system_prompt
    assert "do not add academic apparatus unless compatible or requested" in resolved.system_prompt
    assert "(artifact creative_poem)" in resolved.system_prompt


def test_prompt_manifest_resolver_skips_contract_section_without_metadata():
    cfg = AgentConfig(
        role="Writer",
        model="mock",
        temperature=0.5,
        system_prompt="Base writer prompt.",
    )

    resolved = PromptManifestResolver().resolve_agent_config("writer", cfg, _runtime_manifest())

    assert "[Active Artifact Contract]" not in resolved.system_prompt


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


def test_prompt_manifest_resolver_injects_contract_for_all_runtime_app_agents():
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

    resolved = PromptManifestResolver().resolve_app_config(config, _runtime_manifest_with_contract())

    assert "[Active Artifact Contract]" in resolved.agents["writer"].system_prompt
    assert "[Active Artifact Contract]" in resolved.agents["reviewer"].system_prompt
    assert "[Active Artifact Contract]" not in config.agents["writer"].system_prompt
