from __future__ import annotations

import json
import re
from collections import OrderedDict
from enum import Enum
from typing import Dict, Iterable, List, Mapping, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from academic_pe.core.continuation import ContinuationIntent
from academic_pe.core.document_state import DocumentState


class MergeOperationType(str, Enum):
    preserve = "preserve"
    replace_range = "replace_range"
    replace_tail = "replace_tail"
    append_after = "append_after"
    insert_before = "insert_before"
    expand_section = "expand_section"
    rename_heading = "rename_heading"
    renumber_sections = "renumber_sections"
    update_cross_references = "update_cross_references"
    update_references = "update_references"
    move_terminal_sections_to_end = "move_terminal_sections_to_end"


class MergeOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: MergeOperationType
    target: str = ""
    content_role: Optional[str] = None
    content: Optional[str] = None
    paragraphs: Optional[int] = None
    mode: Optional[str] = None
    purpose: Optional[str] = None
    new_title: Optional[str] = None

    @model_validator(mode="after")
    def validate_operation_shape(self) -> "MergeOperation":
        if self.op == MergeOperationType.replace_tail:
            if not self.paragraphs or self.paragraphs < 1:
                raise ValueError("replace_tail requires paragraphs >= 1")
        if self.op in {
            MergeOperationType.append_after,
            MergeOperationType.insert_before,
            MergeOperationType.expand_section,
            MergeOperationType.replace_range,
        } and not self.content and not self.content_role:
            raise ValueError(f"{self.op.value} requires content or content_role")
        if self.op == MergeOperationType.rename_heading and not self.new_title:
            raise ValueError("rename_heading requires new_title")
        return self


class EditPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: str
    operations: List[MergeOperation] = Field(default_factory=list)
    heading_policies: Dict[str, str] = Field(default_factory=dict)
    red_flags: List[str] = Field(default_factory=list)
    reference_policy: str = "preserve"
    acceptance_checks: List[str] = Field(default_factory=list)


class MergePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_outputs: Dict[str, str] = Field(default_factory=dict)
    assembled_context: Dict[str, str] = Field(default_factory=dict)
    inserted_content: Dict[str, str] = Field(default_factory=dict)
    replaced_ranges: Dict[str, str] = Field(default_factory=dict)
    updated_references: List[str] = Field(default_factory=list)
    reviewer_notes: List[str] = Field(default_factory=list)
    operation_summary: List[dict] = Field(default_factory=list)


class MergeOperationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_outputs: Dict[str, str] = Field(default_factory=dict)
    operations: Optional[List[MergeOperation]] = None
    reviewer_notes: List[str] = Field(default_factory=list)


class MergeOperationPayloadError(ValueError):
    pass


def parse_merge_operation_payload(raw: str) -> MergeOperationPayload:
    text = _extract_json_object(raw)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise MergeOperationPayloadError(f"Writer returned invalid merge-operation JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise MergeOperationPayloadError("Writer merge-operation payload must be a JSON object")

    try:
        payload = MergeOperationPayload.model_validate(data)
    except Exception as exc:
        raise MergeOperationPayloadError(f"Writer merge-operation payload does not match schema: {exc}") from exc

    if not payload.operation_outputs and not payload.operations:
        raise MergeOperationPayloadError("Writer merge-operation payload must include operation_outputs or operations")
    return payload


def required_content_roles(operations: Iterable[MergeOperation | Mapping[str, object]]) -> List[str]:
    roles: List[str] = []
    for raw_operation in operations:
        operation = (
            raw_operation
            if isinstance(raw_operation, MergeOperation)
            else MergeOperation.model_validate(raw_operation)
        )
        if operation.content_role and operation.content is None and operation.content_role not in roles:
            roles.append(operation.content_role)
    return roles


def validate_merge_operation_targets(
    document_state: DocumentState,
    operations: Iterable[MergeOperation | Mapping[str, object]],
) -> List[str]:
    assembled = OrderedDict(
        (section.name, section.content)
        for section in document_state.source_sections
    )
    terminal_names = list(document_state.terminal_sections)
    section_names = set(assembled.keys())
    terminal_set = set(terminal_names)
    issues: List[str] = []

    for raw_operation in operations:
        operation = (
            raw_operation
            if isinstance(raw_operation, MergeOperation)
            else MergeOperation.model_validate(raw_operation)
        )
        target = operation.target
        resolved = _resolve_target(target, assembled, terminal_names)

        if operation.op == MergeOperationType.preserve:
            if target and target != "existing_body" and target not in section_names:
                issues.append(f"preserve target '{target}' does not exist")
            continue

        if operation.op == MergeOperationType.move_terminal_sections_to_end:
            continue

        if operation.op == MergeOperationType.replace_tail:
            if not resolved:
                issues.append(f"replace_tail target '{target}' does not resolve to an existing body section")
            elif resolved in terminal_set:
                issues.append(f"replace_tail target '{target}' resolves to terminal section '{resolved}'")
            continue

        if operation.op == MergeOperationType.append_after:
            if target and not resolved:
                issues.append(f"append_after target '{target}' does not resolve to an existing section")
            elif resolved in terminal_set:
                issues.append(f"append_after target '{target}' resolves to terminal section '{resolved}'")
            continue

        if operation.op == MergeOperationType.insert_before:
            if not target:
                issues.append("insert_before requires a target anchor")
            elif not resolved:
                issues.append(f"insert_before target '{target}' does not resolve to an existing section")
            continue

        if operation.op == MergeOperationType.expand_section:
            if target == "requested_section":
                continue
            if not resolved:
                issues.append(f"expand_section target '{target}' does not resolve to an existing section")
            elif resolved in terminal_set:
                issues.append(f"expand_section target '{target}' resolves to terminal section '{resolved}'")
            continue

        if operation.op == MergeOperationType.replace_range:
            if target == "existing_body":
                continue
            if not resolved:
                issues.append(f"replace_range target '{target}' does not resolve to an existing section")
            continue

        if operation.op == MergeOperationType.update_references:
            if target in {"", "references", "terminal_sections"}:
                continue
            if not resolved:
                issues.append(f"update_references target '{target}' does not resolve to an existing section")
            elif resolved not in terminal_set:
                issues.append(f"update_references target '{target}' resolves to non-terminal section '{resolved}'")
            continue

        if operation.op == MergeOperationType.rename_heading:
            if not resolved:
                issues.append(f"rename_heading target '{target}' does not resolve to an existing section")
            continue

    return issues


def compact_merge_patch_metadata(patch: MergePatch) -> dict:
    return {
        "operation_outputs": patch.operation_outputs,
        "inserted_content": patch.inserted_content,
        "replaced_ranges": patch.replaced_ranges,
        "updated_references": patch.updated_references,
        "reviewer_notes": patch.reviewer_notes,
        "operation_summary": patch.operation_summary,
        "assembled_section_order": list(patch.assembled_context.keys()),
    }


def build_default_edit_plan(intent: ContinuationIntent, terminal_sections: Iterable[str]) -> EditPlan:
    terminals = [section for section in terminal_sections if section]
    operations: List[MergeOperation] = [
        MergeOperation(op=MergeOperationType.preserve, target="existing_body"),
    ]

    insertion_target = terminals[0] if terminals else ""
    if intent == ContinuationIntent.bridge_and_continue:
        operations.append(
            MergeOperation(
                op=MergeOperationType.replace_tail,
                target="last_body_section",
                content_role="smooth_bridge",
                paragraphs=1,
                purpose="smooth_bridge",
            )
        )
        operations.append(_body_insertion_operation(insertion_target, "continuation"))
    elif intent == ContinuationIntent.continue_append:
        operations.append(_body_insertion_operation(insertion_target, "continuation"))
    elif intent == ContinuationIntent.update_references_only:
        operations.append(
            MergeOperation(
                op=MergeOperationType.update_references,
                target=insertion_target or "references",
                content_role="references",
                mode="dedupe_and_merge",
            )
        )
    elif intent == ContinuationIntent.expand_section:
        operations.append(
            MergeOperation(
                op=MergeOperationType.expand_section,
                target="requested_section",
                content_role="expansion",
            )
        )
    elif intent == ContinuationIntent.complete_missing_section:
        operations.append(_body_insertion_operation(insertion_target, "missing_section"))
    elif intent == ContinuationIntent.revise_in_place:
        operations.append(
            MergeOperation(
                op=MergeOperationType.replace_range,
                target="existing_body",
                content_role="revision",
                purpose="revise_in_place",
            )
        )
    elif intent == ContinuationIntent.restructure:
        operations.append(
            MergeOperation(
                op=MergeOperationType.replace_range,
                target="existing_body",
                content_role="restructured_body",
                purpose="restructure",
            )
        )

    if terminals:
        operations.append(MergeOperation(op=MergeOperationType.move_terminal_sections_to_end))

    return EditPlan(
        intent=intent.value,
        operations=operations,
        reference_policy="dedupe_and_merge" if intent == ContinuationIntent.update_references_only else "preserve",
        acceptance_checks=[
            "no_internal_planning_labels",
            "no_body_content_after_terminal_sections",
            "preserve_source_style",
        ],
    )


def apply_merge_operations(
    document_state: DocumentState,
    operations: Iterable[MergeOperation | Mapping[str, object]],
    operation_outputs: Optional[Mapping[str, str]] = None,
) -> MergePatch:
    outputs = dict(operation_outputs or {})
    assembled: "OrderedDict[str, str]" = OrderedDict(
        (section.name, section.content)
        for section in document_state.source_sections
    )
    inserted_content: Dict[str, str] = {}
    replaced_ranges: Dict[str, str] = {}
    updated_references: List[str] = []
    reviewer_notes: List[str] = []
    operation_summary: List[dict] = []

    terminal_names = list(document_state.terminal_sections)

    for raw_operation in operations:
        operation = (
            raw_operation
            if isinstance(raw_operation, MergeOperation)
            else MergeOperation.model_validate(raw_operation)
        )
        content = _operation_content(operation, outputs)

        if operation.op == MergeOperationType.preserve:
            operation_summary.append(_summary(operation, "preserved source content"))
            continue

        if operation.op == MergeOperationType.replace_tail:
            target = _resolve_target(operation.target, assembled, terminal_names)
            if not target:
                reviewer_notes.append("replace_tail skipped because no body target was found")
                operation_summary.append(_summary(operation, "skipped"))
                continue
            assembled[target] = _replace_tail_paragraphs(
                assembled.get(target, ""),
                content,
                operation.paragraphs or 1,
            )
            replaced_ranges[target] = f"tail:{operation.paragraphs or 1}"
            operation_summary.append(_summary(operation, f"replaced tail of {target}"))
            continue

        if operation.op == MergeOperationType.append_after:
            target = _resolve_target(operation.target, assembled, terminal_names)
            section_name = target or _default_body_section_name(assembled, terminal_names)
            assembled[section_name] = _append_block(assembled.get(section_name, ""), content)
            inserted_content[section_name] = content
            operation_summary.append(_summary(operation, f"appended to {section_name}"))
            continue

        if operation.op == MergeOperationType.insert_before:
            target = _resolve_target(operation.target, assembled, terminal_names)
            section_name = _content_section_name(operation, fallback="inserted_content")
            if section_name in assembled:
                assembled[section_name] = _append_block(assembled[section_name], content)
            elif target and target in assembled:
                assembled = _insert_before(assembled, target, section_name, content)
            else:
                assembled[section_name] = content
            inserted_content[section_name] = content
            operation_summary.append(_summary(operation, f"inserted {section_name} before {target or 'end'}"))
            continue

        if operation.op == MergeOperationType.expand_section:
            target = _resolve_target(operation.target, assembled, terminal_names)
            if not target:
                target = _content_section_name(operation, fallback="expanded_section")
            assembled[target] = _append_block(assembled.get(target, ""), content)
            inserted_content[target] = content
            operation_summary.append(_summary(operation, f"expanded {target}"))
            continue

        if operation.op == MergeOperationType.replace_range:
            if operation.target == "existing_body":
                assembled = OrderedDict(_single_body_replacement(content))
                replaced_ranges["existing_body"] = "full"
                operation_summary.append(_summary(operation, "replaced existing body"))
            else:
                target = _resolve_target(operation.target, assembled, terminal_names) or operation.target
                assembled[target] = content
                replaced_ranges[target] = "full"
                operation_summary.append(_summary(operation, f"replaced {target}"))
            continue

        if operation.op == MergeOperationType.update_references:
            target = _resolve_target(operation.target, assembled, terminal_names) or _first_terminal_or_default(
                terminal_names,
                "references",
            )
            assembled[target] = _merge_reference_text(assembled.get(target, ""), content)
            if target not in terminal_names:
                terminal_names.append(target)
            updated_references.append(target)
            operation_summary.append(_summary(operation, f"updated references in {target}"))
            continue

        if operation.op == MergeOperationType.move_terminal_sections_to_end:
            assembled = _move_terminal_sections_to_end(assembled, terminal_names)
            operation_summary.append(_summary(operation, "moved terminal sections to end"))
            continue

        reviewer_notes.append(f"{operation.op.value} is recorded but not applied by the deterministic assembler yet")
        operation_summary.append(_summary(operation, "recorded only"))

    return MergePatch(
        operation_outputs=outputs,
        assembled_context=dict(assembled),
        inserted_content=inserted_content,
        replaced_ranges=replaced_ranges,
        updated_references=updated_references,
        reviewer_notes=reviewer_notes,
        operation_summary=operation_summary,
    )


def _body_insertion_operation(target: str, content_role: str) -> MergeOperation:
    if target:
        return MergeOperation(
            op=MergeOperationType.insert_before,
            target=target,
            content_role=content_role,
        )
    return MergeOperation(
        op=MergeOperationType.append_after,
        target="last_body_section",
        content_role=content_role,
    )


def _operation_content(operation: MergeOperation, outputs: Mapping[str, str]) -> str:
    if operation.content is not None:
        return operation.content
    if operation.content_role and operation.content_role in outputs:
        return outputs[operation.content_role]
    return ""


def _resolve_target(target: str, assembled: Mapping[str, str], terminal_names: List[str]) -> str:
    if not target:
        return ""
    if target == "last_body_section":
        return _last_body_section(assembled, terminal_names)
    if target in {"references", "terminal_sections"}:
        return _first_terminal_or_default(terminal_names, "")
    return target if target in assembled else ""


def _last_body_section(assembled: Mapping[str, str], terminal_names: List[str]) -> str:
    terminal_set = set(terminal_names)
    for section_name in reversed(list(assembled.keys())):
        if section_name not in terminal_set:
            return section_name
    return ""


def _first_terminal_or_default(terminal_names: List[str], default: str) -> str:
    return terminal_names[0] if terminal_names else default


def _default_body_section_name(assembled: Mapping[str, str], terminal_names: List[str]) -> str:
    return _last_body_section(assembled, terminal_names) or "body"


def _content_section_name(operation: MergeOperation, fallback: str) -> str:
    return (operation.content_role or fallback).strip() or fallback


def _append_block(existing: str, content: str) -> str:
    if not existing.strip():
        return content.strip()
    if not content.strip():
        return existing.strip()
    return existing.rstrip() + "\n\n" + content.strip()


def _replace_tail_paragraphs(existing: str, replacement: str, paragraphs: int) -> str:
    blocks = _split_paragraphs(existing)
    replacement = replacement.strip()
    if not blocks:
        return replacement
    kept = blocks[:-paragraphs] if paragraphs < len(blocks) else []
    if replacement:
        kept.append(replacement)
    return "\n\n".join(kept).strip()


def _split_paragraphs(text: str) -> List[str]:
    return [block.strip() for block in text.split("\n\n") if block.strip()]


def _insert_before(
    assembled: "OrderedDict[str, str]",
    target: str,
    section_name: str,
    content: str,
) -> "OrderedDict[str, str]":
    result: "OrderedDict[str, str]" = OrderedDict()
    inserted = False
    for key, value in assembled.items():
        if key == target and not inserted:
            result[section_name] = content.strip()
            inserted = True
        result[key] = value
    if not inserted:
        result[section_name] = content.strip()
    return result


def _merge_reference_text(existing: str, new_content: str) -> str:
    lines = []
    seen = set()
    for line in [*existing.splitlines(), *new_content.splitlines()]:
        cleaned = line.strip()
        if not cleaned:
            continue
        if _is_reference_section_heading(cleaned):
            continue
        key = _reference_dedupe_key(cleaned)
        if key in seen:
            continue
        seen.add(key)
        lines.append(cleaned)
    return "\n".join(lines)


def _reference_dedupe_key(line: str) -> str:
    normalized = re.sub(r"^\s*(?:\[\d+\]|\d+[.)]|[-*])\s*", "", line.strip())
    normalized = re.sub(r"\s+", " ", normalized).strip().lower()
    return normalized


def _is_reference_section_heading(line: str) -> bool:
    normalized = re.sub(r"^\s{0,3}#{1,6}\s+", "", line.strip()).strip().lower()
    return normalized.rstrip(":") in {
        "references",
        "new references",
        "bibliography",
        "works cited",
        "added sources",
        "new sources",
        "sources added",
        "список литературы",
        "источники",
        "новые источники",
        "добавленные источники",
    }


def _move_terminal_sections_to_end(
    assembled: "OrderedDict[str, str]",
    terminal_names: List[str],
) -> "OrderedDict[str, str]":
    terminal_set = set(terminal_names)
    result: "OrderedDict[str, str]" = OrderedDict(
        (key, value)
        for key, value in assembled.items()
        if key not in terminal_set
    )
    for key, value in assembled.items():
        if key in terminal_set:
            result[key] = value
    return result


def _single_body_replacement(content: str) -> Dict[str, str]:
    return {"body": content.strip()}


def _summary(operation: MergeOperation, result: str) -> dict:
    return {
        "op": operation.op.value,
        "target": operation.target,
        "content_role": operation.content_role,
        "result": result,
    }


def _extract_json_object(raw: str) -> str:
    text = (raw or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return text
    return text[start:end + 1]
