"""Patch-first, versioned revisions for an existing document.

The revision flow deliberately operates on an already completed document.  It
never creates a new outline or drafts every section again: a writer is only
asked to return line-replacement blocks for the sections selected by the
revision plan.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Literal, Mapping, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from academic_pe.core.config import AppConfig, SectionPrompt
from academic_pe.core.calculation_audit import CalculationLedger
from academic_pe.core.document_ledger import DocumentLedger
from academic_pe.core.document_state import extract_document_state
from academic_pe.core.language import language_instruction, resolve_output_language
from academic_pe.core.prompting import DEFAULT_PATCH_REVISION_TEMPLATE, DEFAULT_REVIEW_TEMPLATE, DEFAULT_SPECIALIZED_REVIEW_TEMPLATE, render_template
from academic_pe.core.quality_gate import run_all as run_quality_gate
from academic_pe.core.review_payload import merge_review_payloads, parse_review_payload
from academic_pe.review import build_editorial_review_prompt, build_evidence_review_prompt, parse_scoped_review
from academic_pe.core.section_patch import SectionPatchError, add_line_numbers, apply_line_replace_patch
from academic_pe.instructions import InstructionCompiler


class RevisionRequest(BaseModel):
    """A user's optional request to improve a completed document version."""

    model_config = ConfigDict(extra="forbid")

    revision_request_id: str = Field(default_factory=lambda: f"revreq_{uuid4().hex}")
    run_id: str = Field(..., min_length=1)
    base_revision: int = Field(..., ge=1)
    feedback: str = Field(..., min_length=1, max_length=20_000)
    affected_sections: list[str] | None = None

    @field_validator("feedback")
    @classmethod
    def _feedback_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("feedback must not be blank")
        return value

    @field_validator("affected_sections")
    @classmethod
    def _normalize_sections(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        result: list[str] = []
        for raw in value:
            name = str(raw).strip()
            if name and name not in result:
                result.append(name)
        return result or None


class RevisionOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["patch_section", "recalculate", "structural_revision"]
    section: str | None = None
    reason: str
    constraints: list[str] = Field(default_factory=list)
    calculation_ids: list[str] = Field(default_factory=list)


class RevisionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operations: list[RevisionOperation]
    affected_sections: list[str]
    classification: Literal["targeted_revision", "structural_revision"] = "targeted_revision"


class DocumentRevision(BaseModel):
    """Persistent version metadata. ``context_snapshot`` preserves older text."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    revision: int = Field(..., ge=1)
    parent_revision: int | None = Field(default=None, ge=1)
    trigger: Literal["generation", "user_feedback", "automatic_repair"]
    status: Literal["queued", "running", "ready", "failed"] = "queued"
    feedback: str | None = None
    changed_sections: list[str] = Field(default_factory=list)
    artifact_path: str | None = None
    change_summary: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    context_snapshot: dict[str, str] = Field(default_factory=dict)


class RevisionExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context: dict[str, str]
    changed_sections: list[str] = Field(default_factory=list)
    plan: RevisionPlan
    quality_issues: list[str] = Field(default_factory=list)


class Writer(Protocol):
    def process(
        self,
        task: str,
        context: str | None = None,
        document_sections: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> str: ...


_STRUCTURAL_RE = re.compile(
    r"\b(?:restructure|reorganize|rebuild|change\s+structure)\b|"
    r"переструктур|пересобер|измен(?:ите|ить)\s+структур",
    re.IGNORECASE,
)
_CALCULATION_RE = re.compile(
    r"\b(?:calc(?:ulation)?|npv|irr|unit|units|recalculate)\b|"
    r"расч[её]т|пересч[её]т|единиц[аы]",
    re.IGNORECASE,
)


def revision_history(metadata: Mapping[str, Any]) -> list[DocumentRevision]:
    """Read version history, including a safe synthetic initial revision."""

    raw = metadata.get("revisions")
    if isinstance(raw, list):
        items: list[DocumentRevision] = []
        for value in raw:
            try:
                items.append(DocumentRevision.model_validate(value))
            except Exception:
                continue
        if items:
            return sorted(items, key=lambda item: item.revision)

    context = _text_context(metadata.get("context"))
    run_id = str(metadata.get("run_id") or "legacy")
    return [
        DocumentRevision(
            run_id=run_id,
            revision=1,
            parent_revision=None,
            trigger="generation",
            status="ready",
            changed_sections=list(context),
            artifact_path=_artifact_path(metadata),
            change_summary="Initial generated document.",
            created_at=str(metadata.get("timestamp") or datetime.now(timezone.utc).isoformat()),
            context_snapshot=context,
        )
    ]


def initialize_revision_history(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    """Backfill initial revision metadata without changing the current document."""

    history = revision_history(metadata)
    metadata["revisions"] = [item.model_dump(mode="json") for item in history]
    return metadata["revisions"]


def build_revision_plan(
    request: RevisionRequest,
    context: Mapping[str, Any],
    runtime_template: Mapping[str, Any] | None = None,
) -> RevisionPlan:
    document = _text_context(context)
    known = list(document)
    if not known:
        raise ValueError("the completed document has no revisable sections")

    selected = _select_sections(request, document, runtime_template)
    unknown = sorted(set(selected) - set(known))
    if unknown:
        raise ValueError(f"unknown affected section(s): {', '.join(unknown)}")

    structural = bool(_STRUCTURAL_RE.search(request.feedback))
    operations: list[RevisionOperation] = []
    if structural:
        operations.append(
            RevisionOperation(
                type="structural_revision",
                reason="Feedback explicitly requests structural change; preserve existing content unless a patch requires it.",
                constraints=["do_not_create_a_new_document", "preserve_unaffected_sections"],
            )
        )
    for section in selected:
        operations.append(
            RevisionOperation(
                type="patch_section",
                section=section,
                reason=request.feedback,
                constraints=["line_patch_first", "preserve_unaffected_wording", "do_not_rewrite_other_sections"],
            )
        )
    if _CALCULATION_RE.search(request.feedback):
        for section in selected:
            operations.append(
                RevisionOperation(
                    type="recalculate",
                    section=section,
                    reason="User feedback mentions calculations or units.",
                )
            )
    return RevisionPlan(
        operations=operations,
        affected_sections=selected,
        classification="structural_revision" if structural else "targeted_revision",
    )


def execute_patch_revision(
    *,
    request: RevisionRequest,
    config: AppConfig,
    writer: Writer,
    context: Mapping[str, Any],
    runtime_template: Mapping[str, Any] | None = None,
    runtime_prompt_manifest: Mapping[str, Any] | None = None,
    reviewer: Writer | None = None,
    evidence_reviewer: Writer | None = None,
    editorial_reviewer: Writer | None = None,
    document_ledger: DocumentLedger | None = None,
    calculation_ledger: CalculationLedger | None = None,
) -> RevisionExecutionResult:
    """Apply only valid line patches and validate the assembled document.

    An invalid writer answer is deliberately an error.  Falling back to a full
    document rewrite would defeat the primary safety property of this flow.
    """

    original = _text_context(context)
    plan = build_revision_plan(request, original, runtime_template)
    updated = dict(original)
    changed: list[str] = []
    sections = _section_prompts(original, runtime_template)
    runtime_metadata = dict((runtime_prompt_manifest or {}).get("metadata") or {})
    if not runtime_metadata:
        runtime_metadata = dict((runtime_template or {}).get("metadata") or {})
    coverage = runtime_metadata.get("coverage")
    raw_language = getattr(config.pipeline, "language", "auto")
    language = resolve_output_language(request.feedback, str(getattr(raw_language, "value", raw_language)))
    continuation_source = {
        "source_type": "generated",
        "context": original,
        "runtime_template": dict(runtime_template or {}),
        "runtime_prompt_manifest": dict(runtime_prompt_manifest or {}),
    }

    for section_name in plan.affected_sections:
        section = sections[section_name]
        task = render_template(
            DEFAULT_PATCH_REVISION_TEMPLATE,
            {
                "section_brief": InstructionCompiler().compile(
                    "writer",
                    section=section,
                    coverage=coverage,
                    section_names=list(sections),
                    document_ledger=document_ledger,
                    calculation_ledger=calculation_ledger,
                ).section_brief.model_dump(),
                "reviewer_reason": request.feedback,
                "language": language,
                "language_instruction": language_instruction(language),
                "user_topic": "",
                "user_instructions": request.feedback,
                "continuation_context": "This is a user-requested revision of an existing ready document.",
                "academic_mode": getattr(config.pipeline, "academic_mode", False),
                "visualization_required": False,
                "output_dir": config.pipeline.output_dir,
            },
        )
        numbered = add_line_numbers(original[section_name])
        response = writer.process(
            task,
            context=(
                f"[Current section: {section_name}; line-numbered]\n{numbered}\n\n"
                "All other sections are read-only context. Return NO_CHANGES or REPLACE blocks only."
            ),
            document_sections=updated,
        )
        try:
            patched = apply_line_replace_patch(original[section_name], response)
        except SectionPatchError as exc:
            raise SectionPatchError(f"Revision patch for section '{section_name}' is invalid: {exc}") from exc
        if patched != original[section_name]:
            updated[section_name] = patched
            changed.append(section_name)

    document_state = extract_document_state(continuation_source)
    active_document_ledger = document_ledger or document_state.ledger
    active_calculation_ledger = calculation_ledger or document_state.calculation_ledger
    quality = run_quality_gate(
        updated,
        config.quality_gate,
        document_state=document_state.model_dump(mode="json"),
        ledger=active_document_ledger,
        calculation_ledger=active_calculation_ledger,
    )
    if not quality.passed:
        raise ValueError("Revision integrity checks failed: " + "; ".join(quality.issues))
    _review_changed_sections(
        config=config,
        sections=sections,
        context=updated,
        changed_sections=changed,
        reviewer=reviewer,
        evidence_reviewer=evidence_reviewer,
        editorial_reviewer=editorial_reviewer,
        document_ledger=active_document_ledger,
        calculation_ledger=active_calculation_ledger,
        coverage=coverage or {},
    )
    return RevisionExecutionResult(
        context=updated,
        changed_sections=changed,
        plan=plan,
        quality_issues=list(quality.issues),
    )


def append_revision(
    metadata: dict[str, Any],
    revision: DocumentRevision,
) -> None:
    history = revision_history(metadata)
    history = [item for item in history if item.revision != revision.revision]
    history.append(revision)
    metadata["revisions"] = [item.model_dump(mode="json") for item in sorted(history, key=lambda item: item.revision)]


def _review_changed_sections(
    *,
    config: AppConfig,
    sections: Mapping[str, SectionPrompt],
    context: Mapping[str, str],
    changed_sections: list[str],
    reviewer: Writer | None,
    evidence_reviewer: Writer | None,
    editorial_reviewer: Writer | None,
    document_ledger: DocumentLedger,
    calculation_ledger: CalculationLedger,
    coverage: Mapping[str, Any],
) -> None:
    """Review only changed sections while keeping the deterministic global gate."""

    specialized = [("evidence", evidence_reviewer), ("editorial", editorial_reviewer)]
    reviewers = specialized if any(agent is not None for _, agent in specialized) else [("general", reviewer)]
    reviewers = [(role, agent) for role, agent in reviewers if agent is not None]
    if not reviewers or not changed_sections:
        return

    review_sections = [sections[name] for name in changed_sections]
    line_numbered_text = "\n\n".join(
        f"=== Section: {name} ===\n{add_line_numbers(context[name])}"
        for name in changed_sections
    )
    prompt = render_template(
        DEFAULT_REVIEW_TEMPLATE,
        {
            "language": "auto",
            "review_focus": "Review only these user-revised sections; global integrity was checked deterministically.",
            "sections": review_sections,
            "continuation_context": "This is a targeted revision. Unchanged sections are read-only.",
            "academic_mode": getattr(config.pipeline, "academic_mode", False),
            "visualization_required": False,
            "output_dir": config.pipeline.output_dir,
        },
    )
    specialized_prompt = render_template(
        DEFAULT_SPECIALIZED_REVIEW_TEMPLATE,
        {
            "language": "auto",
            "review_focus": "Review only these user-revised sections; global integrity was checked deterministically.",
            "sections": review_sections,
        },
    )
    payloads = []
    for role, agent in reviewers:
        role_prompt = prompt
        if role == "evidence":
            role_prompt = build_evidence_review_prompt(
                specialized_prompt,
                document_ledger=document_ledger,
                calculation_ledger=calculation_ledger,
                coverage=coverage,
            )
        elif role == "editorial":
            role_prompt = build_editorial_review_prompt(specialized_prompt, coverage=coverage)
        response = agent.process(
            role_prompt,
            context=line_numbered_text,
            document_sections=dict(context),
        )
        payload = parse_review_payload(response) if role == "general" else parse_scoped_review(response, role)
        payloads.append(payload)
    merged = merge_review_payloads(payloads)
    if not merged.approved:
        raise ValueError("Revision reviewer rejected changed section(s): " + merged.reason())


def _select_sections(
    request: RevisionRequest,
    context: Mapping[str, str],
    runtime_template: Mapping[str, Any] | None,
) -> list[str]:
    if request.affected_sections:
        return list(request.affected_sections)

    feedback = request.feedback.casefold()
    titles = _section_titles(context, runtime_template)
    matches = [
        name for name in context
        if name.casefold() in feedback or titles[name].casefold() in feedback
    ]
    if matches:
        return matches

    calculation_like = bool(_CALCULATION_RE.search(request.feedback))
    if calculation_like:
        matches = [
            name for name in context
            if re.search(r"calc|financial|model|analysis|расч|финанс|модел|анализ", f"{name} {titles[name]}", re.IGNORECASE)
        ]
        if matches:
            return matches

    # A non-specific comment is reviewed as minimal patches in every section.
    # The patch contract permits NO_CHANGES, so no unmentioned section is
    # rewritten just because its feedback routing was ambiguous.
    return list(context)


def _section_prompts(context: Mapping[str, str], runtime_template: Mapping[str, Any] | None) -> dict[str, SectionPrompt]:
    titles = _section_titles(context, runtime_template)
    raw_sections = runtime_template.get("sections") if isinstance(runtime_template, Mapping) else None
    by_name = {
        str(item.get("name")): item
        for item in raw_sections or []
        if isinstance(item, Mapping) and item.get("name")
    }
    return {
        name: SectionPrompt(
            name=name,
            topic=titles[name],
            instruction=str(by_name.get(name, {}).get("instruction") or "Preserve the completed document except for the requested correction."),
            heading_policy=str(by_name.get(name, {}).get("heading_policy") or "render_required"),
        )
        for name in context
    }


def _section_titles(context: Mapping[str, str], runtime_template: Mapping[str, Any] | None) -> dict[str, str]:
    raw_sections = runtime_template.get("sections") if isinstance(runtime_template, Mapping) else None
    titles = {
        str(item.get("name")): str(item.get("title") or item.get("topic") or item.get("name"))
        for item in raw_sections or []
        if isinstance(item, Mapping) and item.get("name")
    }
    return {name: titles.get(name, re.sub(r"[_-]+", " ", name).strip().title()) for name in context}


def _text_context(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(name): str(content)
        for name, content in value.items()
        if name != "document_plan" and isinstance(content, str) and content.strip()
    }


def _artifact_path(metadata: Mapping[str, Any]) -> str | None:
    for key in ("docx_filename", "pdf_filename"):
        value = metadata.get(key)
        if isinstance(value, str) and value:
            return value
    return None
