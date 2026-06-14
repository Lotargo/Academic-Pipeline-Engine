from __future__ import annotations

import re
from typing import Any

from academic_pe.contracts.models import ArtifactContract


class ContractValidationError(ValueError):
    pass


_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_RESERVED_NAMES = {
    "__import__",
    "__class__",
    "defmacro",
    "eval",
    "exec",
    "import",
    "lambda",
    "load-file",
    "macro",
    "os.system",
    "python-run",
    "read-string",
    "shell",
    "subprocess",
}


def validate_contract(contract: ArtifactContract) -> ArtifactContract:
    issues = contract_validation_issues(contract)
    if issues:
        raise ContractValidationError("; ".join(issues))
    return contract


def contract_validation_issues(contract: ArtifactContract) -> list[str]:
    issues: list[str] = []

    for field_name, value in [
        ("manifest_id", contract.manifest_id),
        ("artifact", contract.artifact),
        ("language", contract.language),
        ("audience", contract.audience),
        ("mode", contract.mode),
        ("execution_mode", contract.execution_mode),
    ]:
        _append_name_issues(issues, field_name, value)

    for index, name in enumerate(contract.style):
        _append_name_issues(issues, f"style[{index}]", name)
    for index, name in enumerate(contract.structure):
        _append_name_issues(issues, f"structure[{index}]", name)
    for index, name in enumerate(contract.forbid):
        _append_name_issues(issues, f"forbid[{index}]", name)
    for key, value in contract.requirements.items():
        _append_name_issues(issues, f"requirements.{key}", key)
        _append_value_issues(issues, f"requirements.{key}", value)

    return issues


def _append_name_issues(issues: list[str], field_name: str, value: str) -> None:
    normalized = value.strip()
    if not normalized:
        issues.append(f"{field_name} must not be empty")
        return
    if not _SAFE_NAME_RE.match(normalized):
        issues.append(f"{field_name} must be a safe atom name")
    if normalized.casefold() in _RESERVED_NAMES:
        issues.append(f"{field_name} uses reserved contract name '{value}'")


def _append_value_issues(issues: list[str], path: str, value: Any) -> None:
    if value is None or isinstance(value, bool | int | float | str):
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _append_value_issues(issues, f"{path}[{index}]", item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                issues.append(f"{path} contains non-string key {key!r}")
                continue
            _append_name_issues(issues, f"{path}.{key}", key)
            _append_value_issues(issues, f"{path}.{key}", item)
        return
    issues.append(f"{path} contains unsupported value type {type(value).__name__}")
