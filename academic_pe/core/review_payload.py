"""Structured reviewer payload with compatibility for the legacy text format."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


REVIEW_ROLE_GUIDANCE = {
    "evidence": (
        "EvidenceReviewer: verify SourceCard/ClaimCard coverage, external numbers, "
        "dates, calculations, units, assumptions, and contradictions."
    ),
    "editorial": (
        "EditorialReviewer: verify section ownership, repetition, transitions, "
        "register, genre, audience, internal leakage, and terminology consistency."
    ),
    "general": "Review the complete artifact against its contract and user constraints.",
}


def reviewer_role_guidance(role: str) -> str:
    return REVIEW_ROLE_GUIDANCE.get(str(role).casefold(), REVIEW_ROLE_GUIDANCE["general"])


class ReviewIssue(BaseModel):
    model_config = ConfigDict(extra="ignore")

    section: str = "general"
    line: int | None = Field(default=None, ge=1)
    severity: str = "major"
    code: str = "REVIEW_ISSUE"
    message: str


class StructuredReviewPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    approved: bool
    reviewer_role: str = "general"
    issues: list[ReviewIssue] = Field(default_factory=list)
    summary: str = ""

    def reason(self) -> str:
        if self.approved:
            return ""
        lines: list[str] = []
        if self.summary.strip():
            lines.append(self.summary.strip())
        for issue in self.issues:
            location = f"[{issue.section}]"
            if issue.line is not None:
                location += f" line {issue.line}"
            lines.append(f"- {location}: {issue.message}")
        return "\n".join(lines) or "Reviewer rejected the document without a structured explanation."


def _json_candidate(raw: str) -> dict[str, Any] | None:
    text = raw.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            value = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return value if isinstance(value, dict) else None


def parse_review_payload(raw: str | StructuredReviewPayload) -> StructuredReviewPayload:
    if isinstance(raw, StructuredReviewPayload):
        return raw

    candidate = _json_candidate(raw)
    if candidate is not None and "approved" in candidate:
        issues = candidate.get("issues") or []
        if not isinstance(issues, list):
            issues = []
        return StructuredReviewPayload(
            approved=bool(candidate.get("approved")),
            reviewer_role=str(candidate.get("reviewer_role") or "general"),
            issues=issues,
            summary=str(candidate.get("summary") or ""),
        )

    if raw.strip().upper() == "APPROVED":
        return StructuredReviewPayload(approved=True)

    text = raw.strip()
    summary = re.sub(r"^REJECTED\s*:?\s*", "", text, flags=re.IGNORECASE).strip()
    issues: list[dict[str, Any]] = []
    for line in summary.splitlines():
        match = re.match(r"^-?\s*\[([^\]]+)\](?:\s*:\s*line\s+(\d+))?\s*:?\s*(.+)$", line, re.IGNORECASE)
        if not match:
            continue
        issues.append(
            {
                "section": match.group(1).strip() or "general",
                "line": int(match.group(2)) if match.group(2) else None,
                "message": match.group(3).strip(),
            }
        )
    return StructuredReviewPayload(approved=False, issues=issues, summary=summary)


def merge_review_payloads(payloads: list[StructuredReviewPayload]) -> StructuredReviewPayload:
    """Combine independent evidence/editorial decisions into one gate result."""

    if not payloads:
        return StructuredReviewPayload(approved=True)
    issues = [issue for payload in payloads for issue in payload.issues]
    summaries = [payload.summary.strip() for payload in payloads if payload.summary.strip()]
    roles = ",".join(payload.reviewer_role for payload in payloads)
    return StructuredReviewPayload(
        approved=all(payload.approved for payload in payloads),
        reviewer_role=roles,
        issues=issues,
        summary="; ".join(summaries),
    )
