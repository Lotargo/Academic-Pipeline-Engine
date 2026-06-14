from __future__ import annotations


def contract_guidance() -> str:
    return (
        "Reviewer: check for genre, style, audience, structure, prompt, and forbidden-clause drift against the "
        "contract. Treat standard_mode and academic_mode clauses as binding. Reject incompatible academicization, "
        "bureaucracy, missing user constraints, and AI/meta markers."
    )
