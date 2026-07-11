from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Quantity(BaseModel):
    """A reproducible numeric value and its declared unit."""

    model_config = ConfigDict(extra="forbid")

    value: float = Field(allow_inf_nan=False)
    unit: str = ""
    source: Optional[str] = None


class CalculationEntry(BaseModel):
    """One deterministic calculation used by a document section."""

    model_config = ConfigDict(extra="forbid")

    calculation_id: str = Field(pattern=r"^CALC-\d{3,}$")
    expression: str = Field(min_length=1)
    inputs: dict[str, Quantity] = Field(default_factory=dict)
    expected_result: Quantity
    section_owner: str = Field(min_length=1)
    depends_on: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_input_names(self) -> "CalculationEntry":
        invalid_names = [name for name in self.inputs if not name.isidentifier()]
        if invalid_names:
            raise ValueError(f"Calculation inputs must be valid identifiers: {invalid_names}")
        if self.calculation_id in self.depends_on:
            raise ValueError("A calculation cannot depend on itself")
        return self


class CalculationLedger(BaseModel):
    """Stable calculation records for one document run or continuation."""

    model_config = ConfigDict(extra="forbid")

    entries: list[CalculationEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_entries(self) -> "CalculationLedger":
        ids = [entry.calculation_id for entry in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("Calculation ledger contains duplicate calculation IDs")
        known_ids = set(ids)
        for entry in self.entries:
            unknown = set(entry.depends_on) - known_ids
            if unknown:
                raise ValueError(
                    f"Calculation {entry.calculation_id} depends on unknown calculations: {sorted(unknown)}"
                )
        return self

    def register(self, entry: CalculationEntry | Mapping[str, Any]) -> CalculationEntry:
        return self.register_many([entry])[0]

    def register_many(
        self,
        entries: list[CalculationEntry | Mapping[str, Any]],
    ) -> list[CalculationEntry]:
        """Atomically register calculation records, including forward dependencies."""
        candidates = [
            entry if isinstance(entry, CalculationEntry) else CalculationEntry.model_validate(entry)
            for entry in entries
        ]
        candidate_ids = [entry.calculation_id for entry in candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("Calculation ledger batch contains duplicate calculation IDs")

        existing_ids = {entry.calculation_id for entry in self.entries}
        duplicates = existing_ids.intersection(candidate_ids)
        if duplicates:
            raise ValueError(f"Calculation ID already registered: {sorted(duplicates)[0]}")

        combined = [*self.entries, *candidates]
        CalculationLedger(entries=combined)
        self.entries = combined
        return candidates

    def upsert_many_for_section(
        self,
        section_owner: str,
        entries: list[CalculationEntry | Mapping[str, Any]],
    ) -> list[CalculationEntry]:
        """Replace only same-section records with matching IDs after a section revision."""
        candidates = [
            entry if isinstance(entry, CalculationEntry) else CalculationEntry.model_validate(entry)
            for entry in entries
        ]
        if any(entry.section_owner != section_owner for entry in candidates):
            raise ValueError("Calculation entry owner does not match the section being updated")
        candidate_ids = [entry.calculation_id for entry in candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("Calculation ledger batch contains duplicate calculation IDs")
        for existing in self.entries:
            if existing.calculation_id in candidate_ids and existing.section_owner != section_owner:
                raise ValueError(
                    f"Calculation ID {existing.calculation_id} belongs to section {existing.section_owner!r}"
                )
        combined = [
            entry for entry in self.entries if entry.calculation_id not in set(candidate_ids)
        ] + candidates
        CalculationLedger(entries=combined)
        self.entries = combined
        return candidates


@dataclass(frozen=True)
class CalculationAuditResult:
    passed: bool
    issues: list[str] = field(default_factory=list)
    evaluated: dict[str, Quantity] = field(default_factory=dict)


@dataclass(frozen=True)
class _DimensionedValue:
    value: float
    dimensions: dict[str, int]


_UNIT_ALIASES = {
    "": {},
    "1": {},
    "unitless": {},
    "%": {},
    "percent": {},
    "процент": {},
    "проценты": {},
    "руб": {"currency": 1},
    "rub": {"currency": 1},
    "rur": {"currency": 1},
    "usd": {"currency": 1},
    "eur": {"currency": 1},
    "m": {"length": 1},
    "метр": {"length": 1},
    "метры": {"length": 1},
    "m2": {"length": 2},
    "m²": {"length": 2},
    "кв.м": {"length": 2},
    "кв. м": {"length": 2},
    "kg": {"mass": 1},
    "кг": {"mass": 1},
    "s": {"time": 1},
    "sec": {"time": 1},
    "second": {"time": 1},
    "сек": {"time": 1},
    "ч": {"time": 1},
    "hour": {"time": 1},
}
_CALC_MARKER_RE = re.compile(r"\[(?P<id>CALC-\d{3,})\]")
_TEXT_RESULT_RE = re.compile(
    r"^\s*(?:=|:|—|-)?\s*(?P<value>[+-]?\d+(?:[.,]\d+)?)"
    r"(?:\s*(?P<unit>[A-Za-zА-Яа-яЁё².%]+(?:\s+[A-Za-zА-Яа-яЁё².%]+)?))?"
)


def audit_calculations(
    ledger: CalculationLedger | Mapping[str, Any] | None,
    *,
    context: Mapping[str, str] | None = None,
    tolerance: float = 1e-6,
) -> CalculationAuditResult:
    """Recompute registered formulas without executing model-provided code.

    Expressions intentionally support only arithmetic and a small set of numeric
    functions. This makes the audit deterministic and keeps untrusted document
    data out of the general-purpose sandbox.
    """
    if ledger is None:
        issues = _text_reference_issues(context or {}, {})
        return CalculationAuditResult(passed=not issues, issues=issues)
    if isinstance(ledger, CalculationLedger):
        resolved = ledger
    else:
        try:
            resolved = CalculationLedger.model_validate(ledger)
        except (TypeError, ValueError) as exc:
            return CalculationAuditResult(passed=False, issues=[f"Invalid calculation ledger: {exc}"])
    if tolerance < 0:
        return CalculationAuditResult(passed=False, issues=["Calculation tolerance must be non-negative."])

    issues: list[str] = []
    evaluated: dict[str, Quantity] = {}
    pending = list(resolved.entries)
    while pending:
        ready = [entry for entry in pending if all(dependency in evaluated for dependency in entry.depends_on)]
        if not ready:
            issues.extend(
                f"Calculation {entry.calculation_id} has cyclic or failed dependencies: "
                f"{', '.join(entry.depends_on)}."
                for entry in pending
            )
            break
        for entry in ready:
            pending.remove(entry)
            try:
                inputs = {
                    name: _DimensionedValue(quantity.value, _unit_dimensions(quantity.unit))
                    for name, quantity in entry.inputs.items()
                }
                for dependency in entry.depends_on:
                    dependency_result = evaluated[dependency]
                    inputs[_calculation_name(dependency)] = _DimensionedValue(
                        dependency_result.value,
                        _unit_dimensions(dependency_result.unit),
                    )
                actual = _evaluate_expression(entry.expression, inputs)
            except (ValueError, SyntaxError, ZeroDivisionError, OverflowError) as exc:
                issues.append(f"Calculation {entry.calculation_id} cannot be evaluated safely: {exc}")
                continue

            expected_dimensions = _unit_dimensions(entry.expected_result.unit)
            if actual.dimensions != expected_dimensions:
                issues.append(
                    f"Calculation {entry.calculation_id} has incompatible units: expression yields "
                    f"{_format_dimensions(actual.dimensions)}, expected {entry.expected_result.unit or 'unitless'}."
                )
                continue
            if not math.isclose(actual.value, entry.expected_result.value, rel_tol=tolerance, abs_tol=tolerance):
                issues.append(
                    f"Calculation {entry.calculation_id} result mismatch: expression yields {actual.value:g}, "
                    f"expected {entry.expected_result.value:g} (tolerance {tolerance:g})."
                )
                continue
            evaluated[entry.calculation_id] = entry.expected_result

    issues.extend(_text_reference_issues(context or {}, evaluated))
    return CalculationAuditResult(passed=not issues, issues=issues, evaluated=evaluated)


def _calculation_name(calculation_id: str) -> str:
    return calculation_id.lower().replace("-", "_")


def _unit_dimensions(unit: str) -> dict[str, int]:
    normalized = " ".join((unit or "").strip().casefold().split())
    if normalized in _UNIT_ALIASES:
        return dict(_UNIT_ALIASES[normalized])
    raise ValueError(f"unsupported unit {unit!r}")


def _format_dimensions(dimensions: Mapping[str, int]) -> str:
    if not dimensions:
        return "unitless"
    return " * ".join(
        name if exponent == 1 else f"{name}^{exponent}"
        for name, exponent in sorted(dimensions.items())
    )


def _evaluate_expression(expression: str, variables: Mapping[str, _DimensionedValue]) -> _DimensionedValue:
    parsed = ast.parse(expression, mode="eval")
    return _evaluate_node(parsed.body, variables)


def _evaluate_node(node: ast.AST, variables: Mapping[str, _DimensionedValue]) -> _DimensionedValue:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return _DimensionedValue(float(node.value), {})
    if isinstance(node, ast.Name):
        if node.id not in variables:
            raise ValueError(f"unknown input {node.id!r}")
        return variables[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _evaluate_node(node.operand, variables)
        return _DimensionedValue(value.value if isinstance(node.op, ast.UAdd) else -value.value, value.dimensions)
    if isinstance(node, ast.BinOp):
        left = _evaluate_node(node.left, variables)
        right = _evaluate_node(node.right, variables)
        if isinstance(node.op, (ast.Add, ast.Sub)):
            if left.dimensions != right.dimensions:
                raise ValueError("addition/subtraction requires compatible units")
            return _DimensionedValue(
                left.value + right.value if isinstance(node.op, ast.Add) else left.value - right.value,
                left.dimensions,
            )
        if isinstance(node.op, ast.Mult):
            return _DimensionedValue(left.value * right.value, _combine_dimensions(left.dimensions, right.dimensions, 1))
        if isinstance(node.op, ast.Div):
            if right.value == 0:
                raise ZeroDivisionError("division by zero")
            return _DimensionedValue(left.value / right.value, _combine_dimensions(left.dimensions, right.dimensions, -1))
        if isinstance(node.op, ast.Pow):
            if right.dimensions:
                raise ValueError("exponent must be unitless")
            if not float(right.value).is_integer():
                raise ValueError("exponent must be an integer")
            exponent = int(right.value)
            return _DimensionedValue(left.value**exponent, {key: value * exponent for key, value in left.dimensions.items()})
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"abs", "min", "max", "round"}:
        values = [_evaluate_node(argument, variables) for argument in node.args]
        if not values:
            raise ValueError(f"{node.func.id} requires at least one argument")
        if node.func.id == "abs":
            if len(values) != 1:
                raise ValueError("abs accepts exactly one argument")
            return _DimensionedValue(abs(values[0].value), values[0].dimensions)
        if node.func.id in {"min", "max"}:
            if any(value.dimensions != values[0].dimensions for value in values[1:]):
                raise ValueError(f"{node.func.id} requires compatible units")
            function = min if node.func.id == "min" else max
            return _DimensionedValue(function(value.value for value in values), values[0].dimensions)
        if node.func.id == "round":
            if len(values) == 1:
                return _DimensionedValue(round(values[0].value), values[0].dimensions)
            if len(values) == 2 and not values[1].dimensions:
                return _DimensionedValue(round(values[0].value, int(values[1].value)), values[0].dimensions)
            raise ValueError("round accepts a value and an optional unitless number of digits")
    raise ValueError(f"unsupported expression component {ast.dump(node, include_attributes=False)}")


def _combine_dimensions(left: Mapping[str, int], right: Mapping[str, int], direction: int) -> dict[str, int]:
    result = dict(left)
    for name, exponent in right.items():
        result[name] = result.get(name, 0) + direction * exponent
        if result[name] == 0:
            del result[name]
    return result


def _text_reference_issues(context: Mapping[str, str], evaluated: Mapping[str, Quantity]) -> list[str]:
    issues: list[str] = []
    for section, text in context.items():
        for line_no, line in enumerate((text or "").splitlines(), 1):
            for marker in _CALC_MARKER_RE.finditer(line):
                calculation_id = marker.group("id")
                if calculation_id not in evaluated:
                    issues.append(
                        f"Section '{section}' references failed or unknown calculation [{calculation_id}] at line {line_no}."
                    )
                    continue
                text_result = _TEXT_RESULT_RE.match(line[marker.end():])
                if not text_result:
                    continue
                displayed_value = float(text_result.group("value").replace(",", "."))
                expected = evaluated[calculation_id]
                if not math.isclose(displayed_value, expected.value, rel_tol=1e-6, abs_tol=1e-6):
                    issues.append(
                        f"Section '{section}' displays {displayed_value:g} for [{calculation_id}] at line {line_no}, "
                        f"but the calculation ledger records {expected.value:g}."
                    )
                displayed_unit = (text_result.group("unit") or "").rstrip(".,;:")
                if displayed_unit:
                    try:
                        units_match = _unit_dimensions(displayed_unit) == _unit_dimensions(expected.unit)
                    except ValueError:
                        units_match = False
                    if not units_match:
                        issues.append(
                            f"Section '{section}' displays unit {displayed_unit!r} for [{calculation_id}] at line {line_no}, "
                            f"but the calculation ledger records {expected.unit or 'unitless'}.")
    return issues
