from academic_pe.contracts import compile_artifact_contract, render_contract_sexpr
from academic_pe.manifests import ArtifactManifestResolver
from academic_pe.manifests.models import ArtifactManifest, ArtifactModeOverlay


def test_contract_renderer_is_stable_and_escapes_strings():
    manifest = ArtifactManifest(
        id="unknown_freeform",
        version=1,
        artifact_type="unknown_freeform",
        style=["natural", "preserve_user_intent"],
        forbid=["academic_drift", "title_page"],
        content_boundaries={
            "adult_content": {
                "explicitness": "user_requested",
                "require_all_characters_adult": True,
                "require_consent": True,
                "forbid": ["minors", "coercion", "non_consensual"],
            }
        },
        requirements={
            "theme": 'quote "inside"',
            "nested": {"b": 2, "a": "first"},
        },
    )

    contract = compile_artifact_contract(
        manifest,
        language="ru",
        extra_requirements={"min_lines": 12},
    )

    rendered = render_contract_sexpr(contract)

    assert rendered == render_contract_sexpr(contract)
    assert '(artifact unknown_freeform)' in rendered
    assert '(language ru)' in rendered
    assert '(clauses standard_mode)' in rendered
    assert '(forbid academic_drift title_page)' in rendered
    assert '(content_boundary adult_content ' in rendered
    assert '(explicitness "user_requested")' in rendered
    assert '(require_consent true)' in rendered
    assert '(forbid ("minors" "coercion" "non_consensual"))' in rendered
    assert '(requirement min_lines 12)' in rendered
    assert '(requirement nested ((a "first") (b 2)))' in rendered
    assert '(requirement theme "quote \\"inside\\"")' in rendered


def test_contract_renderer_escapes_newlines_and_backslashes():
    manifest = ArtifactManifest(
        id="unknown_freeform",
        artifact_type="unknown_freeform",
        requirements={
            "path_note": "C:\\tmp\\artifact\nnext line",
        },
    )

    rendered = render_contract_sexpr(compile_artifact_contract(manifest))

    assert '(requirement path_note "C:\\\\tmp\\\\artifact\\nnext line")' in rendered


def test_unknown_artifact_fallback_renders_preserve_first_contract():
    manifests = {
        "academic_paper": ArtifactManifest(
            id="academic_paper",
            artifact_type="academic_paper",
            forbid=["unsupported_claims"],
        ),
        "unknown_freeform": ArtifactManifest(
            id="unknown_freeform",
            artifact_type="unknown_freeform",
            style=["preserve_user_intent", "natural"],
            structure=["preserve_apparent_structure"],
            forbid=["academic_drift", "invented_structure", "rubric"],
        ),
    }

    resolved = ArtifactManifestResolver(manifests=manifests).resolve(
        topic="Odd moon ledger",
        instructions="Keep my custom two-column fragment form.",
    )

    assert resolved.manifest.id == "unknown_freeform"
    assert resolved.evidence.confidence == 0.25
    assert "(artifact unknown_freeform)" in resolved.contract_sexpr
    assert "(style preserve_user_intent natural)" in resolved.contract_sexpr
    assert "(structure preserve_apparent_structure)" in resolved.contract_sexpr
    assert "(forbid academic_drift invented_structure rubric)" in resolved.contract_sexpr


def test_academic_overlay_does_not_force_visualization_for_poem():
    manifest = ArtifactManifest(
        id="creative_poem",
        artifact_type="creative_poem",
        forbid=["academic_drift", "forced_visualization"],
        modes={
            "academic": ArtifactModeOverlay(
                add_forbid=["research_paper_structure"],
                visualization_policy="forbidden",
            )
        },
    )

    contract = compile_artifact_contract(manifest, execution_mode="academic")

    assert contract.visualization_required is False
    assert contract.clauses == ["academic_mode"]
    assert "research_paper_structure" in contract.forbid
    assert "forced_visualization" in contract.forbid


def test_academic_paper_overlay_can_require_visualization():
    manifest = ArtifactManifest(
        id="academic_paper",
        artifact_type="academic_paper",
        modes={
            "academic": ArtifactModeOverlay(
                add_requirements={"evidence_discipline": True},
                visualization_policy="required",
            )
        },
    )

    contract = compile_artifact_contract(manifest, execution_mode="academic")

    assert contract.visualization_required is True
    assert "(clauses academic_mode)" in render_contract_sexpr(contract)
    assert contract.requirements["evidence_discipline"] is True
