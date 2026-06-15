from __future__ import annotations

from typing import Dict, Optional

from academic_pe.agents.base import BaseAgent, StreamCallback
from academic_pe.core.researcher import load_research_findings, run_researcher_pool


class ResearcherAgent(BaseAgent):
    """Deterministic source-research agent used by the Planning phase."""

    def run_research(self, queries: list[str], run_dir: str) -> str:
        clean_queries = [q.strip() for q in queries if str(q).strip()]
        if not clean_queries:
            return ""
        run_researcher_pool(clean_queries, run_dir)
        return load_research_findings(run_dir)

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
