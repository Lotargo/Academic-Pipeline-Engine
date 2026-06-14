from pathlib import Path


def test_manifest_contract_architecture_doc_records_boundaries():
    doc_path = Path("docs/MANIFEST_CONTRACT_ARCHITECTURE.md")

    text = doc_path.read_text(encoding="utf-8")

    assert "Manifest And Contract Architecture" in text
    assert "`academic_pe.manifests`" in text
    assert "`academic_pe.contracts`" in text
    assert "`academic_pe.agent_adapters`" in text
    assert "`academic_pe.server`" in text
    assert "must not contain executable code" in text
    assert "No eval" in text
    assert "a separate\nADR" in text
    assert "Reviewer LLM remains the external qualitative gate" in text
