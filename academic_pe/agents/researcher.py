from __future__ import annotations

import json
import logging
from typing import Dict, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field

from academic_pe.agents.base import BaseAgent, StreamCallback
from academic_pe.core.llm import _call_provider_generate
from academic_pe.core.document_ledger import SourceCard
from academic_pe.core.researcher import load_research_findings, run_researcher_pool

logger = logging.getLogger(__name__)


class CuratedClaim(BaseModel):
    """A researcher claim whose evidence must resolve to a crawled source URL."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    source_urls: list[str] = Field(default_factory=list)
    status: str = "unsupported"
    section_owner: Optional[str] = None


class ResearchCuration(BaseModel):
    """Structured researcher output safe for the document evidence ledger."""

    model_config = ConfigDict(extra="forbid")

    notes: str = ""
    source_cards: list[SourceCard] = Field(default_factory=list)
    claims: list[CuratedClaim] = Field(default_factory=list)


class ResearcherAgent(BaseAgent):
    """Source-research agent used by the Planning phase."""

    def run_research(
        self,
        queries: list[str],
        run_dir: str,
        instruction_guidance: Sequence[str] = (),
    ) -> str:
        self.last_curation: Optional[ResearchCuration] = None
        if not instruction_guidance:
            instruction_guidance = getattr(self, "instruction_guidance", ())
        clean_queries = [q.strip() for q in queries if str(q).strip()]
        if not clean_queries:
            return ""
        raw_results = run_researcher_pool(clean_queries, run_dir)
        findings = load_research_findings(run_dir)
        provider = str(getattr(self.config.provider, "value", self.config.provider))
        if provider == "mock" and isinstance(raw_results, list):
            curation = _curation_from_search_results(raw_results)
            if curation.source_cards:
                self.last_curation = curation
                return _render_research_curation(curation)
        curated = self._curate_findings(clean_queries, findings, instruction_guidance)
        curation = _parse_research_curation(curated)
        if curation is not None:
            curation = _validate_curation_sources(curation, findings)
            self.last_curation = curation
            return _render_research_curation(curation)
        return curated

    def _curate_findings(
        self,
        queries: list[str],
        findings: str,
        instruction_guidance: Sequence[str] = (),
    ) -> str:
        if not findings.strip():
            return ""
        provider = str(getattr(self.config.provider, "value", self.config.provider))
        if provider == "mock":
            return findings

        task = (
            "Convert raw search results into SourceCards for a planning agent. Do not draft document prose.\n"
            "Return one JSON object only with keys notes, source_cards, and claims. Each source_cards item must contain "
            "source_id (SRC-001 sequence), title, url, publication_date or null, source_type, reliability, notes, "
            "reliability_notes, supported_claims, relevant_excerpt, and conflicts_with. Each claim contains text, "
            "source_urls, status (supported, assumption, disputed, unsupported), and optional section_owner. "
            "Use only URLs, titles, and excerpts present in Raw Findings. Reject crawler errors, SEO filler, duplicated pages, "
            "and results whose content cannot support a relevant claim. Record stale dates, blocked/partial extraction, weak "
            "snippets, source dependence, and conflicts explicitly. Prefer primary/official material for rules and product facts, "
            "peer-reviewed or institutional material for research claims, and reputable dated reporting for current events. "
            "A supported claim must cite at least one retained source URL. Never invent a URL, publication date, or personal observation.\n\n"
            "[Queries]\n"
            + "\n".join(f"- {query}" for query in queries)
            + ("\n\n[Selected Research Skills]\n" + "\n".join(f"- {item}" for item in instruction_guidance) if instruction_guidance else "")
            + "\n\n[Raw Findings]\n"
            + findings
        )
        try:
            return _call_provider_generate(
                self.llm,
                system_prompt=self.config.system_prompt,
                user_prompt=task,
                model=self.config.model,
                temperature=self.config.temperature,
                reasoning_effort=getattr(self.config.reasoning_effort, "value", self.config.reasoning_effort),
            )
        except Exception as exc:
            logger.warning("Researcher LLM curation failed; using raw findings. Error: %s", exc)
            return findings

    def process(
        self,
        task_description: str,
        context: Optional[str] = None,
        on_delta: Optional[StreamCallback] = None,
        document_sections: Optional[Dict[str, str]] = None,
    ) -> str:
        queries = [line.strip() for line in task_description.splitlines() if line.strip()]
        findings = self.run_research(queries, context or "exports")
        if on_delta and findings:
            on_delta(findings)
        return findings


def _parse_research_curation(value: str) -> Optional[ResearchCuration]:
    raw = value.strip()
    if raw.startswith("```json") and raw.endswith("```"):
        raw = raw[len("```json"): -3].strip()
    try:
        return ResearchCuration.model_validate(json.loads(raw))
    except (TypeError, ValueError):
        return None


def _render_research_curation(curation: ResearchCuration) -> str:
    if not curation.source_cards:
        return curation.notes.strip()
    parts: list[str] = []
    if curation.source_cards:
        parts.append("[Source Cards]")
        for card in curation.source_cards:
            parts.append(card.model_dump_json(exclude_none=True))
    if curation.notes.strip():
        parts.append("[Research Notes]\n" + curation.notes.strip())
    return "\n".join(parts).strip()


def _validate_curation_sources(curation: ResearchCuration, raw_findings: str) -> ResearchCuration:
    if not curation.source_cards:
        # Legacy curation payloads had claims only. They remain readable for old
        # stored providers, while the active SourceCard protocol is validated below.
        return curation
    source_cards = [
        card for card in curation.source_cards
        if card.url and card.url in raw_findings and card.title in raw_findings
    ]
    retained_urls = {card.url for card in source_cards if card.url}
    claims: list[CuratedClaim] = []
    for claim in curation.claims:
        urls = [url for url in claim.source_urls if url in retained_urls or url in raw_findings]
        status = claim.status
        if status == "supported" and not urls:
            status = "unsupported"
        claims.append(claim.model_copy(update={"source_urls": urls, "status": status}))
    return curation.model_copy(update={"source_cards": source_cards, "claims": claims})


def _curation_from_search_results(raw_results: list[object]) -> ResearchCuration:
    cards: list[SourceCard] = []
    seen_urls: set[str] = set()
    for query_result in raw_results:
        if not isinstance(query_result, dict):
            continue
        for item in query_result.get("results", []):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            url = str(item.get("url") or "").strip()
            content = str(item.get("content") or "").strip()
            snippet = str(item.get("snippet") or "").strip()
            if not title or not url or url in seen_urls or content.lower().startswith("error crawling"):
                continue
            seen_urls.add(url)
            extraction = str(item.get("extraction_method") or "direct")
            excerpt = " ".join((content or snippet).split())[:800]
            cards.append(SourceCard(
                source_id=f"SRC-{len(cards) + 1:03d}",
                title=title,
                url=url,
                source_type="web",
                reliability="unverified",
                reliability_notes=[f"extraction_method={extraction}", "Requires claim-level verification"],
                relevant_excerpt=excerpt,
            ))
    return ResearchCuration(source_cards=cards)
