from typing import Optional


def contract_guidance(artifact_id: Optional[str] = None) -> str:
    return (
        "Researcher: search only when the contract or user request requires current facts or sources. Do not force "
        "citations, source hunts, or research apparatus into creative, personal, or otherwise source-free artifacts. "
        "For continuation work with an existing reference_registry, preserve the source citation style, deduplicate "
        "against registry entries, and return candidate source entries for registry merge instead of editorial labels "
        "such as 'new references' or 'added sources'."
    )
