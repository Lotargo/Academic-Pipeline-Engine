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
