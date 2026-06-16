from __future__ import annotations

import logging
from typing import Dict, Optional

from academic_pe.agents.base import BaseAgent, StreamCallback
from academic_pe.core.llm import _call_provider_generate
from academic_pe.core.researcher import load_research_findings, run_researcher_pool

logger = logging.getLogger(__name__)


class ResearcherAgent(BaseAgent):
    """Source-research agent used by the Planning phase."""

    def run_research(self, queries: list[str], run_dir: str) -> str:
        clean_queries = [q.strip() for q in queries if str(q).strip()]
        if not clean_queries:
            return ""
        run_researcher_pool(clean_queries, run_dir)
        findings = load_research_findings(run_dir)
        return self._curate_findings(clean_queries, findings)

    def _curate_findings(self, queries: list[str], findings: str) -> str:
        if not findings.strip():
            return ""
        provider = str(getattr(self.config.provider, "value", self.config.provider))
        if provider == "mock":
            return findings

        task = (
            "Curate the raw web research findings for a planning agent.\n"
            "Return compact, source-grounded notes only. Preserve source titles and URLs. "
            "Group findings by query when useful, include relevant snippets or facts, and flag uncertainty. "
            "Do not draft the final document and do not invent sources.\n\n"
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
