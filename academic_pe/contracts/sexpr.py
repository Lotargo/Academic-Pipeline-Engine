from __future__ import annotations

from typing import Any

from academic_pe.contracts.models import ArtifactContract


def render_contract_sexpr(contract: ArtifactContract) -> str:
    lines = ["(document"]
    lines.append(f"  (manifest { _atom(contract.manifest_id) } {contract.manifest_version})")
    lines.append(f"  (artifact {_atom(contract.artifact)})")
    lines.append(f"  (language {_atom(contract.language)})")
    if contract.style:
        lines.append("  (style " + " ".join(_atom(item) for item in contract.style) + ")")
    lines.append(f"  (audience {_atom(contract.audience)})")
    lines.append(f"  (mode {_atom(contract.mode)})")
    lines.append(f"  (execution_mode {_atom(contract.execution_mode)})")
    if contract.structure:
        lines.append("  (structure " + " ".join(_atom(item) for item in contract.structure) + ")")
    if contract.forbid:
        lines.append("  (forbid " + " ".join(_atom(item) for item in contract.forbid) + ")")
    for key in sorted(contract.requirements):
        lines.append(f"  (requirement {_atom(key)} {_value(contract.requirements[key])})")
    lines.append(f"  (visualization_required {_bool(contract.visualization_required)})")
    lines.append(")")
    return "\n".join(lines)


def _value(value: Any) -> str:
    if isinstance(value, bool):
        return _bool(value)
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, list):
        return "(" + " ".join(_value(item) for item in value) + ")"
    if isinstance(value, dict):
        parts = []
        for key in sorted(value):
            parts.append(f"({_atom(str(key))} {_value(value[key])})")
        return "(" + " ".join(parts) + ")"
    return _string(str(value))


def _atom(value: str) -> str:
    if value.replace("_", "").replace("-", "").isalnum():
        return value
    return _string(value)


def _bool(value: bool) -> str:
    return "true" if value else "false"


def _string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'
