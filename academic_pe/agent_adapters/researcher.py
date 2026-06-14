from typing import Optional


def contract_guidance(artifact_id: Optional[str] = None) -> str:
    return (
        "Researcher: search only when the contract or user request requires current facts or sources. Do not force "
        "citations, source hunts, or research apparatus into creative, personal, or otherwise source-free artifacts."
    )
