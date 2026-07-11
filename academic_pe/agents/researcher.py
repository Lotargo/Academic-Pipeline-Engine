from __future__ import annotations

import json
import logging
from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from academic_pe.agents.base import BaseAgent, StreamCallback
from academic_pe.core.llm import _call_provider_generate
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
    claims: list[CuratedClaim] = Field(default_factory=list)


class ResearcherAgent(BaseAgent):
    """Source-research agent used by the Planning phase."""

    def run_research(self, queries: list[str], run_dir: str) -> str:
        self.last_curation: Optional[ResearchCuration] = None
        clean_queries = [q.strip() for q in queries if str(q).strip()]
        if not clean_queries:
            return ""
        run_researcher_pool(clean_queries, run_dir)
        findings = load_research_findings(run_dir)
        curated = self._curate_findings(clean_queries, findings)
        curation = _parse_research_curation(curated)
        if curation is not None:
            self.last_curation = curation
            return curation.notes
        return curated

    def _curate_findings(self, queries: list[str], findings: str) -> str:
        if not findings.strip():
            return ""
        provider = str(getattr(self.config.provider, "value", self.config.provider))
        if provider == "mock":
            return findings

        task = (
            "Curate the raw web research findings for a planning agent.\n"
            "Return a JSON object only, with keys 'notes' and 'claims'. 'notes' is compact, "
            "source-grounded planning context. Each claim must contain text, source_urls, status "
            "(supported, assumption, disputed, or unsupported), and optional section_owner. "
            "Use only source_urls present in Raw Findings; do not invent URLs. Preserve source titles and URLs exactly. "
            "Group findings by query when useful. Extract concrete facts, dates, definitions, statistics, "
            "names, and competing viewpoints that directly help the requested artifact. "
            "Prefer primary, official, standards, documentation, peer-reviewed, institutional, or reputable news sources. "
            "Flag weak evidence, paywalled/blocked pages, stale dates, conflicting claims, and thin snippets. "
            "Ignore boilerplate, cookie banners, navigation text, ads, SEO filler, and duplicated source text. "
            "If a source was fetched through a reader fallback, treat it as useful but still verify relevance from the URL/title/snippet. "
            "Do not draft the final document, do not invent sources, and do not turn raw crawler text into unsupported claims.\n\n"
            "[Queries]\n"
            + "\n".join(f"- {query}" for query in queries)
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
