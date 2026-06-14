import pytest
from academic_pe.manifests import ArtifactManifestResolver


def test_execution_mode_poem():
    resolver = ArtifactManifestResolver()

    # Standard Mode
    resolved_std = resolver.resolve(
        topic="Autumn",
        instructions="Write a poem.",
        academic_mode=False,
    )
    assert resolved_std.manifest.id == "creative_poem"
    assert resolved_std.contract.clauses == ["standard_mode"]
    assert resolved_std.contract.visualization_required is False
    assert "research_paper_structure" not in resolved_std.contract.forbid  # added only in academic mode
    assert "forced_visualization" in resolved_std.contract.forbid

    # Academic Mode
    resolved_acad = resolver.resolve(
        topic="Autumn",
        instructions="Write a poem.",
        academic_mode=True,
    )
    assert resolved_acad.manifest.id == "creative_poem"
    assert resolved_acad.contract.clauses == ["academic_mode"]
    assert resolved_acad.contract.visualization_required is False
    assert "research_paper_structure" in resolved_acad.contract.forbid  # added via academic overlay
    assert "forced_visualization" in resolved_acad.contract.forbid


def test_execution_mode_story():
    resolver = ArtifactManifestResolver()

    # Standard Mode
    resolved_std = resolver.resolve(
        topic="Forest",
        instructions="Write a story.",
        academic_mode=False,
    )
    assert resolved_std.manifest.id == "creative_story"
    assert resolved_std.contract.clauses == ["standard_mode"]
    assert resolved_std.contract.visualization_required is False
    assert "research_paper_structure" not in resolved_std.contract.forbid

    # Academic Mode
    resolved_acad = resolver.resolve(
        topic="Forest",
        instructions="Write a story.",
        academic_mode=True,
    )
    assert resolved_acad.manifest.id == "creative_story"
    assert resolved_acad.contract.clauses == ["academic_mode"]
    assert resolved_acad.contract.visualization_required is False
    assert "research_paper_structure" in resolved_acad.contract.forbid


def test_execution_mode_readme():
    resolver = ArtifactManifestResolver()

    # Standard Mode
    resolved_std = resolver.resolve(
        topic="Project",
        instructions="Write a README.",
        academic_mode=False,
    )
    assert resolved_std.manifest.id == "technical_readme"
    assert resolved_std.contract.clauses == ["standard_mode"]
    assert "rigor" not in resolved_std.contract.requirements
    assert "citations" in resolved_std.contract.forbid

    # Academic Mode
    resolved_acad = resolver.resolve(
        topic="Project",
        instructions="Write a README.",
        academic_mode=True,
    )
    assert resolved_acad.manifest.id == "technical_readme"
    assert resolved_acad.contract.clauses == ["academic_mode"]
    assert resolved_acad.contract.requirements["rigor"] == "reproducibility_and_limitations"
    assert "citations" in resolved_acad.contract.forbid  # citations still forbidden!


def test_execution_mode_academic_paper():
    resolver = ArtifactManifestResolver()

    # Standard Mode
    resolved_std = resolver.resolve(
        topic="Physics",
        instructions="Write an academic paper.",
        academic_mode=False,
    )
    assert resolved_std.manifest.id == "academic_paper"
    assert resolved_std.contract.clauses == ["standard_mode"]
    assert "evidence_discipline" not in resolved_std.contract.requirements
    assert resolved_std.contract.visualization_required is False

    # Academic Mode
    resolved_acad = resolver.resolve(
        topic="Physics",
        instructions="Write an academic paper.",
        academic_mode=True,
    )
    assert resolved_acad.manifest.id == "academic_paper"
    assert resolved_acad.contract.clauses == ["academic_mode"]
    assert resolved_acad.contract.requirements["evidence_discipline"] is True
    assert resolved_acad.contract.visualization_required is True
