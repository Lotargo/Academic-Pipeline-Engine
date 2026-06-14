from pathlib import Path

from academic_pe.contracts import compile_artifact_contract
from academic_pe.manifests import ArtifactManifestLoader


def test_artifact_manifest_loader_reads_temp_yaml(tmp_path):
    manifest_path = tmp_path / "config" / "artifact_manifests.yaml"
    manifest_path.parent.mkdir()
    manifest_path.write_text(
        """
artifacts:
  - id: creative_poem
    version: 2
    artifact_type: creative_poem
    style: lyrical
    audience: general
    forbid: [academic_drift, forced_visualization]
    content_boundaries:
      adult_content:
        explicitness: user_requested
        require_all_characters_adult: true
        require_consent: true
        forbid: [minors, coercion, non_consensual]
    modes:
      academic:
        add_forbid: [research_paper_structure]
        visualization_policy: forbidden
""",
        encoding="utf-8",
    )

    manifests = ArtifactManifestLoader(manifest_path).load()

    poem = manifests["creative_poem"]
    assert poem.version == 2
    assert poem.style == ["lyrical"]
    assert poem.content_boundaries["adult_content"]["require_consent"] is True
    assert "minors" in poem.content_boundaries["adult_content"]["forbid"]
    assert poem.modes["academic"].visualization_policy == "forbidden"


def test_artifact_manifest_loader_rejects_duplicates_in_temp_yaml(tmp_path):
    manifest_path = tmp_path / "artifact_manifests.yaml"
    manifest_path.write_text(
        """
artifacts:
  - id: duplicate
    artifact_type: report
  - id: duplicate
    artifact_type: creative_poem
""",
        encoding="utf-8",
    )

    try:
        ArtifactManifestLoader(manifest_path).load()
        assert False, "Expected duplicate manifest id to be rejected."
    except ValueError as exc:
        assert "Duplicate artifact manifest id" in str(exc)


def test_default_manifests_encode_standard_vs_academic_boundaries():
    manifest_path = Path(__file__).resolve().parents[2] / "config" / "artifact_manifests.yaml"
    manifests = ArtifactManifestLoader(manifest_path).load()

    standard_poem = compile_artifact_contract(manifests["creative_poem"], execution_mode="standard")
    academic_poem = compile_artifact_contract(manifests["creative_poem"], execution_mode="academic")
    academic_readme = compile_artifact_contract(manifests["technical_readme"], execution_mode="academic")
    academic_paper = compile_artifact_contract(manifests["academic_paper"], execution_mode="academic")

    assert standard_poem.execution_mode == "standard"
    assert standard_poem.visualization_required is False
    assert academic_poem.visualization_required is False
    assert "research_paper_structure" in academic_poem.forbid
    assert "forced_visualization" in academic_poem.forbid
    assert academic_readme.visualization_required is False
    assert academic_readme.requirements["rigor"] == "reproducibility_and_limitations"
    assert academic_paper.visualization_required is True
    assert academic_paper.requirements["evidence_discipline"] is True
