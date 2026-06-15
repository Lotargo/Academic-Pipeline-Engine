from typing import Optional


def contract_guidance(artifact_id: Optional[str] = None) -> str:
    return (
        "Planner: choose section structure compatible with the contract; do not add academic apparatus unless "
        "compatible with mode clauses or requested. Preserve continuation structure when present, and prefer artifact-native "
        "sections over generic research-paper sections. When a continuation has an existing reference_registry, plan source "
        "changes through that registry and the references terminal section rather than adding raw 'new sources' prose."
    )
