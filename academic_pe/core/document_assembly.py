"""Deterministic document assembly primitives for the document pipeline.

The assembly stage deliberately performs small, predictable transformations. It
does not ask an LLM to rewrite the document; it orders sections, coalesces
duplicate reference sections, and records the coverage contract used by
validation and reviewers.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CoverageMatrix(BaseModel):
    """Map conceptual responsibilities to the sections that own them."""

    model_config = ConfigDict(extra="forbid")

    coverage: dict[str, list[str]] = Field(default_factory=dict)

    @field_validator("coverage")
    @classmethod
    def _validate_coverage(cls, value: dict[str, list[str]]) -> dict[str, list[str]]:
        normalized: dict[str, list[str]] = {}
        for responsibility, owners in value.items():
            key = str(responsibility).strip()
            if not key:
                raise ValueError("coverage responsibility must not be empty")
            unique_owners: list[str] = []
            for owner in owners:
                name = str(owner).strip()
                if name and name not in unique_owners:
                    unique_owners.append(name)
            if not unique_owners:
                raise ValueError(f"coverage responsibility '{key}' has no owner")
            normalized[key] = unique_owners
        return normalized


class AssemblyResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context: dict[str, str]
    coverage: CoverageMatrix
    merged_reference_sections: list[str] = Field(default_factory=list)
    section_order: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


_TERMINAL_NAME_RE = re.compile(
    r"(?:reference|references|bibliograph|source|литератур|источник|appendix|приложен|glossary|глоссар)",
    re.IGNORECASE,
)
_REFERENCE_NAME_RE = re.compile(
    r"(?:reference|references|bibliograph|source|литератур|источник)",
    re.IGNORECASE,
)


def _field(item: Any, name: str, default: Any = None) -> Any:
    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


def _is_terminal(name: str, spec: Any | None) -> bool:
    role = str(_field(spec, "semantic_role", "")).casefold()
    return role in {"reference_section", "appendix", "glossary"} or bool(_TERMINAL_NAME_RE.search(name))


def _is_reference_section(name: str, spec: Any | None) -> bool:
    role = str(_field(spec, "semantic_role", "")).casefold()
    return role == "reference_section" or bool(_REFERENCE_NAME_RE.search(name))


def _default_coverage(section_names: Sequence[str]) -> dict[str, list[str]]:
    names = [str(name) for name in section_names]

    def matching(*needles: str) -> list[str]:
        return [name for name in names if any(needle in name.casefold() for needle in needles)]

    coverage: dict[str, list[str]] = {}
    intro = matching("introduction", "intro", "введен")
    conclusion = matching("conclusion", "summary", "заключ", "вывод")
    limitations = matching("limitation", "огранич")
    financial = matching("financial", "finance", "эконом", "финанс")
    social = matching("social", "социал")
    if intro or conclusion:
        coverage["central_thesis"] = [*intro, *conclusion]
    if limitations:
        coverage["methodological_limitations"] = limitations
    if financial:
        coverage["financial_assumptions"] = financial
    if social:
        coverage["social_risks"] = social
    if conclusion:
        coverage["future_research"] = conclusion
    return coverage


def build_coverage_matrix(
    raw: Mapping[str, Any] | CoverageMatrix | None,
    section_names: Sequence[str],
) -> CoverageMatrix:
    """Validate planner-provided coverage, or derive a conservative default."""

    if isinstance(raw, CoverageMatrix):
        matrix = raw
    else:
        candidate: Any = raw.get("coverage") if isinstance(raw, Mapping) and "coverage" in raw else raw
        if candidate is None:
            candidate = _default_coverage(section_names)
        if not isinstance(candidate, Mapping):
            raise ValueError("coverage must be an object mapping responsibilities to section names")
        normalized_candidate: dict[str, list[str]] = {}
        for key, value in candidate.items():
            if isinstance(value, str):
                value = [value]
            if not isinstance(value, Sequence) or isinstance(value, (bytes, bytearray)):
                raise ValueError(f"coverage responsibility '{key}' must contain section names")
            normalized_candidate[str(key)] = [str(owner) for owner in value]
        matrix = CoverageMatrix(coverage=normalized_candidate)

    known = set(section_names)
    unknown = sorted({owner for owners in matrix.coverage.values() for owner in owners if owner not in known})
    if unknown:
        raise ValueError(f"coverage references unknown section(s): {', '.join(unknown)}")
    return matrix


def _dedupe_reference_lines(text: str, seen: set[str]) -> list[str]:
    result: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        key = re.sub(r"^\s*(?:\[\d+\]|\d+[.)]|[-*])\s*", "", stripped).casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(line.rstrip())
    return result


def assemble_document(
    context: Mapping[str, str],
    sections: Sequence[Any],
    coverage: Mapping[str, Any] | CoverageMatrix | None = None,
) -> AssemblyResult:
    """Assemble sections in contract order without rewriting their prose."""

    specs = {str(_field(section, "name")): section for section in sections if _field(section, "name")}
    configured_names = [str(_field(section, "name")) for section in sections if _field(section, "name")]
    section_names = [name for name in configured_names if name in context]
    unknown_names = [name for name in context if name not in specs and name != "document_plan"]
    section_names.extend(name for name in unknown_names if name not in section_names)

    body_names = [name for name in section_names if not _is_terminal(name, specs.get(name))]
    terminal_names = [name for name in section_names if _is_terminal(name, specs.get(name))]
    ordered_names = (["document_plan"] if "document_plan" in context else []) + body_names + terminal_names

    assembled = {name: str(context.get(name) or "") for name in ordered_names}
    reference_names = [name for name in terminal_names if _is_reference_section(name, specs.get(name))]
    merged_reference_sections: list[str] = []
    if len(reference_names) > 1:
        primary = reference_names[0]
        seen: set[str] = set()
        merged_lines: list[str] = []
        for name in reference_names:
            lines = _dedupe_reference_lines(assembled.get(name, ""), seen)
            if lines:
                merged_lines.extend(lines)
            if name != primary:
                merged_reference_sections.append(name)
        assembled[primary] = "\n".join(merged_lines)
        for name in merged_reference_sections:
            assembled.pop(name, None)
        ordered_names = [name for name in ordered_names if name not in merged_reference_sections]
    elif reference_names:
        primary = reference_names[0]
        seen = set()
        assembled[primary] = "\n".join(_dedupe_reference_lines(assembled[primary], seen))

    matrix = build_coverage_matrix(coverage, [name for name in ordered_names if name != "document_plan"])
    return AssemblyResult(
        context={name: assembled[name] for name in ordered_names if name in assembled},
        coverage=matrix,
        merged_reference_sections=merged_reference_sections,
        section_order=ordered_names,
    )
