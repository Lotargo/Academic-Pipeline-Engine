from __future__ import annotations

import json
from collections.abc import Mapping


def build_editorial_review_prompt(
    base_prompt: str,
    *,
    coverage: Mapping[str, object] | None = None,
    terminology: Mapping[str, str] | None = None,
) -> str:
    """Build an editorial-only task without source or calculation registries."""
    editorial_state = {
        "coverage": dict(coverage or {}),
        "terminology": dict(terminology or {}),
    }
    return (
        f"{base_prompt}\n\n"
        "You are EditorialReviewer. Check only section ownership, duplicated claims or conclusions, "
        "transitions, local coherence, terminology, genre, audience/register, visible planning labels, "
        "and sentences that add no content. Do not adjudicate source reliability, citation support, "
        "calculations, numeric correctness, or units; those belong to EvidenceReviewer. "
        "Set reviewer_role to 'editorial'.\n\n"
        "[Editorial Review State JSON]\n"
        + json.dumps(editorial_state, ensure_ascii=False, sort_keys=True)
    )
