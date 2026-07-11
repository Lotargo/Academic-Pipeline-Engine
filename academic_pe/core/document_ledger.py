from __future__ import annotations

import re
from typing import Iterable, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceCard(BaseModel):
    """A stable, metadata-only source record shared by every document section."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(pattern=r"^SRC-\d{3,}$")
    title: str = Field(min_length=1)
    url: Optional[str] = None
    publication_date: Optional[str] = None
    source_type: str = "unknown"
    reliability: str = "unknown"
    notes: list[str] = Field(default_factory=list)


class ClaimCard(BaseModel):
    """A claim and its evidence status; it never owns a section-local citation ID."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(pattern=r"^CLAIM-\d{3,}$")
    text: str = Field(min_length=1)
    source_ids: list[str] = Field(default_factory=list)
    status: Literal["supported", "assumption", "disputed", "unsupported"] = "unsupported"
    section_owner: Optional[str] = None


class DocumentLedger(BaseModel):
    """Source and claim registry for one document generation or continuation."""

    model_config = ConfigDict(extra="forbid")

    sources: list[SourceCard] = Field(default_factory=list)
    claims: list[ClaimCard] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_references(self) -> "DocumentLedger":
        source_ids = [source.source_id for source in self.sources]
        claim_ids = [claim.claim_id for claim in self.claims]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("Document ledger contains duplicate source IDs")
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("Document ledger contains duplicate claim IDs")

        known_sources = set(source_ids)
        for claim in self.claims:
            missing = set(claim.source_ids) - known_sources
            if missing:
                raise ValueError(f"Claim {claim.claim_id} references unknown source IDs: {sorted(missing)}")
            if claim.status == "supported" and not claim.source_ids:
                raise ValueError(f"Supported claim {claim.claim_id} requires at least one source ID")
        return self

    def register_source(
        self,
        *,
        title: str,
        url: Optional[str] = None,
        publication_date: Optional[str] = None,
        source_type: str = "unknown",
        reliability: str = "unknown",
        notes: Optional[Iterable[str]] = None,
    ) -> SourceCard:
        cleaned_title = _clean_text(title)
        if not cleaned_title:
            raise ValueError("Source title must not be empty")
        cleaned_url = _clean_url(url)
        source_key = (cleaned_url or "", _normalize_title(cleaned_title))
        for source in self.sources:
            existing_key = (_clean_url(source.url) or "", _normalize_title(source.title))
            if source_key == existing_key:
                return source

        source = SourceCard(
            source_id=f"SRC-{len(self.sources) + 1:03d}",
            title=cleaned_title,
            url=cleaned_url,
            publication_date=_clean_text(publication_date) or None,
            source_type=_clean_text(source_type) or "unknown",
            reliability=_clean_text(reliability) or "unknown",
            notes=[_clean_text(note) for note in notes or [] if _clean_text(note)],
        )
        self.sources.append(source)
        return source

    def register_claim(
        self,
        *,
        text: str,
        source_ids: Optional[Iterable[str]] = None,
        status: Literal["supported", "assumption", "disputed", "unsupported"] = "unsupported",
        section_owner: Optional[str] = None,
    ) -> ClaimCard:
        claim = ClaimCard(
            claim_id=f"CLAIM-{len(self.claims) + 1:03d}",
            text=_clean_text(text),
            source_ids=list(source_ids or []),
            status=status,
            section_owner=_clean_text(section_owner) or None,
        )
        candidate = DocumentLedger(sources=self.sources, claims=[*self.claims, claim])
        self.claims = candidate.claims
        return claim

    def source_cards_context(self) -> str:
        """Render a compact source-only context safe to pass to Writer."""
        lines: list[str] = []
        for source in self.sources:
            lines.append(f"[{source.source_id}] {source.title}")
            if source.url:
                lines.append(f"URL: {source.url}")
            lines.append(f"Type: {source.source_type}; reliability: {source.reliability}")
            if source.publication_date:
                lines.append(f"Published: {source.publication_date}")
            for note in source.notes:
                lines.append(f"Note: {note}")
            lines.append("")
        return "\n".join(lines).strip()

    def writer_context(self) -> str:
        """Render the verified evidence records the Writer is allowed to cite."""
        parts: list[str] = []
        source_cards = self.source_cards_context()
        if source_cards:
            parts.append("[Source Cards]\n" + source_cards)

        if self.claims:
            claim_lines: list[str] = []
            for claim in self.claims:
                source_ids = ", ".join(claim.source_ids) or "none"
                claim_lines.extend(
                    [
                        f"[{claim.claim_id}] status={claim.status}; sources={source_ids}",
                        f"Claim: {claim.text}",
                    ]
                )
                if claim.section_owner:
                    claim_lines.append(f"Section owner: {claim.section_owner}")
                claim_lines.append("")
            parts.append("[Claim Cards]\n" + "\n".join(claim_lines).strip())

        return "\n\n".join(parts)


def ledger_from_references(entries: Iterable[object]) -> DocumentLedger:
    ledger = DocumentLedger()
    for entry in entries:
        raw_text = _clean_text(getattr(entry, "raw_text", ""))
        if not raw_text:
            continue
        ledger.register_source(
            title=raw_text,
            source_type="continuation_reference",
            reliability="inherited",
            notes=[f"section={_clean_text(getattr(entry, 'section_name', 'unknown')) or 'unknown'}"],
        )
    return ledger


def _clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _clean_url(value: object) -> Optional[str]:
    url = _clean_text(value)
    return url.rstrip("/") or None


def _normalize_title(value: str) -> str:
    return _clean_text(value).casefold()
