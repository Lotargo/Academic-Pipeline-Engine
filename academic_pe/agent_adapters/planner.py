from typing import Optional


def contract_guidance(artifact_id: Optional[str] = None) -> str:
    return (
        "Planner: choose section structure compatible with the contract; do not add academic apparatus unless "
        "compatible with mode clauses or requested. Preserve continuation structure when present, and prefer artifact-native "
        "sections over generic research-paper sections."
    )
