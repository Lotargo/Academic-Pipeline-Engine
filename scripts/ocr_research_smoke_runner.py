from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from academic_pe.agents.base import DefaultAgent
from academic_pe.core.config import (
    AgentConfig,
    AppConfig,
    LatexGateConfig,
    MarkdownGateConfig,
    PipelineConfig,
    QualityGateConfig,
    SectionPrompt,
    TemplateMode,
    VolumeGateConfig,
    load_config,
)
from academic_pe.core.llm import MockProvider
from academic_pe.core.ocr import count_tokens, process_file_via_mistral_ocr, split_markdown_into_sections
from academic_pe.core.orchestrator import Orchestrator
from academic_pe.core.orchestrator import create_orchestrator_from_config
from academic_pe.core.secrets import is_secret_configured

NOTE_PATH = ROOT / "dev_docs" / "OCR_RESEARCH_SMOKE_NOTES.md"
LOG_DIR = ROOT / "exports" / "_smoke_ocr_research"


@dataclass(frozen=True)
class SmokeScenario:
    scenario_id: str
    title: str
    required_checks: tuple[str, ...]


@dataclass
class SmokeResult:
    passed: bool
    issues: list[str]
    details: dict[str, Any]
    blocked: bool = False


class FlushNote:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, line: str = "") -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()


class SmokeLog:
    def __init__(self, scenario_id: str, path: Path):
        self.scenario_id = scenario_id
        self.path = path
        self.events: list[dict[str, Any]] = []
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def event(self, kind: str, message: str, **extra: Any) -> None:
        payload = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "scenario": self.scenario_id,
            "kind": kind,
            "message": message,
            **extra,
        }
        self.events.append(payload)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
            f.flush()


class RecordingAgent(DefaultAgent):
    def __init__(self, config: AgentConfig, response: str):
        super().__init__(config, MockProvider())
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def process(self, task_description: str, context: Optional[str] = None, on_delta=None, document_sections=None) -> str:
        self.calls.append(
            {
                "task": task_description,
                "context": context or "",
                "document_sections": dict(document_sections or {}),
            }
        )
        if on_delta:
            on_delta(self.response)
        return self.response


class RecordingResearcher(RecordingAgent):
    def __init__(self, config: AgentConfig, findings: str):
        super().__init__(config, response=findings)
        self.research_calls: list[dict[str, Any]] = []

    def run_research(self, queries: list[str], run_dir: str) -> str:
        self.research_calls.append({"queries": list(queries), "run_dir": run_dir})
        return self.response


def scenario_catalog() -> Dict[str, SmokeScenario]:
    return {
        "web_search_off_standard_pipeline": SmokeScenario(
            scenario_id="web_search_off_standard_pipeline",
            title="Web search off keeps the standard pipeline",
            required_checks=(
                "researcher is not called",
                "search query generation is not called",
                "planner still creates the document plan",
            ),
        ),
        "web_search_on_researcher_boundary": SmokeScenario(
            scenario_id="web_search_on_researcher_boundary",
            title="Web search on uses Planner + Researcher, not Writer",
            required_checks=(
                "planner generates/receives research context",
                "researcher is called once with planned queries",
                "writer receives only planner-curated source notes",
                "raw search findings do not reach writer",
            ),
        ),
        "reference_attachment_planner_only": SmokeScenario(
            scenario_id="reference_attachment_planner_only",
            title="Reference attachment is planner-only raw context",
            required_checks=(
                "raw reference text reaches planner",
                "raw reference text does not reach writer",
                "writer receives planner-curated plan only",
            ),
        ),
        "uploaded_continuation_source": SmokeScenario(
            scenario_id="uploaded_continuation_source",
            title="Uploaded Markdown continuation source is converted to source sections",
            required_checks=(
                "uploaded Markdown splits into continuation context sections",
                "runtime template is created from uploaded headings",
                "terminal references are recognized",
            ),
        ),
        "mistral_ocr_direct": SmokeScenario(
            scenario_id="mistral_ocr_direct",
            title="Direct Mistral OCR smoke with configured key",
            required_checks=(
                "mistral secret is configured",
                "generated PDF is OCR'd through Mistral API",
                "unique marker survives OCR",
            ),
        ),
        "real_llm_web_research": SmokeScenario(
            scenario_id="real_llm_web_research",
            title="Real Planner/Writer LLM web research smoke",
            required_checks=(
                "configured real Planner/Writer secrets are available",
                "Researcher returns non-empty search findings",
                "Planner creates a source-aware plan",
                "Writer drafts from planner-curated context without raw reference leakage",
            ),
        ),
    }


def _agent_config(role: str) -> AgentConfig:
    return AgentConfig(role=role, model="mock", temperature=0.0, system_prompt=f"{role}.")


def _smoke_config(output_dir: Path) -> AppConfig:
    return AppConfig(
        agents={
            "writer": _agent_config("Writer"),
            "planner": _agent_config("Planner"),
            "researcher": _agent_config("Researcher"),
        },
        pipeline=PipelineConfig(
            sections=[SectionPrompt(name="body", topic="Body", instruction="Draft the body.")],
            output_dir=str(output_dir),
            academic_mode=False,
        ),
        quality_gate=QualityGateConfig(
            volume=VolumeGateConfig(enabled=False),
            latex=LatexGateConfig(enabled=False),
            markdown=MarkdownGateConfig(enabled=False),
        ),
    )


def _run_orchestrator(
    *,
    output_dir: Path,
    web_search_enabled: bool,
    planner_response: str,
    writer_response: str,
    research_findings: str = "",
    reference_materials: Optional[list[dict[str, str]]] = None,
) -> tuple[Orchestrator, RecordingAgent, RecordingAgent, RecordingResearcher]:
    config = _smoke_config(output_dir)
    writer = RecordingAgent(config.agents["writer"], writer_response)
    planner = RecordingAgent(config.agents["planner"], planner_response)
    researcher = RecordingResearcher(config.agents["researcher"], research_findings)
    orchestrator = Orchestrator(
        writer=writer,
        planner=planner,
        researcher=researcher,
        config=config,
        reference_materials=reference_materials,
        web_search_enabled=web_search_enabled,
    )
    orchestrator.user_topic = "Smoke topic"
    orchestrator.user_instructions = "Smoke instructions"
    orchestrator._generate_search_queries = lambda: ["smoke query"]  # type: ignore[method-assign]
    orchestrator.run_pipeline(render_artifact=False)
    return orchestrator, planner, writer, researcher


def _contains(calls: list[dict[str, Any]], needle: str) -> bool:
    return any(needle in call.get("task", "") or needle in call.get("context", "") for call in calls)


def check_web_search_off(output_dir: Path, log: SmokeLog) -> SmokeResult:
    orchestrator, planner, writer, researcher = _run_orchestrator(
        output_dir=output_dir,
        web_search_enabled=False,
        planner_response="Plan without web search.",
        writer_response="Draft without web search.",
    )
    issues = []
    if researcher.research_calls:
        issues.append("researcher was called while web_search_enabled=False")
    if orchestrator.search_findings:
        issues.append("search_findings was populated while web_search_enabled=False")
    if not planner.calls:
        issues.append("planner was not called in standard pipeline")
    if orchestrator.context.get("document_plan") != "Plan without web search.":
        issues.append("planner output was not stored as document_plan")
    log.event("scenario_check", "web search off checks completed", researcher_calls=len(researcher.research_calls))
    return SmokeResult(not issues, issues, {"planner_calls": len(planner.calls), "writer_calls": len(writer.calls)})


def check_web_search_on_boundary(output_dir: Path, log: SmokeLog) -> SmokeResult:
    raw_marker = "RAW_SEARCH_MARKER_SHOULD_STAY_WITH_PLANNER"
    curated_note = "Use Source A (https://source.test) for the data point."
    orchestrator, planner, writer, researcher = _run_orchestrator(
        output_dir=output_dir,
        web_search_enabled=True,
        planner_response=f"Curated plan. {curated_note}",
        writer_response="Draft using curated source note.",
        research_findings=f"Source A URL: https://source.test\nRelevant excerpt: {raw_marker}",
    )
    issues = []
    if researcher.research_calls != [{"queries": ["smoke query"], "run_dir": str(output_dir)}]:
        issues.append("researcher was not called exactly once with generated query")
    if not _contains(planner.calls, raw_marker):
        issues.append("raw research findings did not reach planner")
    if _contains(writer.calls, raw_marker):
        issues.append("raw research findings leaked to writer")
    if not _contains(writer.calls, curated_note):
        issues.append("planner-curated source note did not reach writer through document plan")
    if orchestrator.search_findings == "":
        issues.append("orchestrator did not store researcher findings")
    log.event("scenario_check", "web search boundary checks completed", researcher_calls=len(researcher.research_calls))
    return SmokeResult(not issues, issues, {"planner_calls": len(planner.calls), "writer_calls": len(writer.calls)})


def check_reference_attachment_planner_only(output_dir: Path, log: SmokeLog) -> SmokeResult:
    raw_marker = "RAW_REFERENCE_MARKER_SHOULD_STAY_WITH_PLANNER"
    curated_note = "Use the attached report only for the historical timeline."
    _orchestrator, planner, writer, _researcher = _run_orchestrator(
        output_dir=output_dir,
        web_search_enabled=False,
        planner_response=f"Curated plan. {curated_note}",
        writer_response="Draft from curated attachment note.",
        reference_materials=[{"filename": "reference.md", "content": raw_marker}],
    )
    issues = []
    if not _contains(planner.calls, raw_marker):
        issues.append("raw reference material did not reach planner")
    if _contains(writer.calls, raw_marker):
        issues.append("raw reference material leaked to writer")
    if not _contains(writer.calls, curated_note):
        issues.append("planner-curated reference note did not reach writer through document plan")
    log.event("scenario_check", "reference attachment boundary checks completed")
    return SmokeResult(not issues, issues, {"planner_calls": len(planner.calls), "writer_calls": len(writer.calls)})


def check_uploaded_continuation_source(output_dir: Path, log: SmokeLog) -> SmokeResult:
    markdown = """# Introduction
Existing argument text.

## Development
Continuation base text.

# References
1. Existing source.
"""
    context, runtime_template = split_markdown_into_sections(markdown)
    issues = []
    if set(context) != {"introduction", "development", "references"}:
        issues.append(f"unexpected continuation sections: {sorted(context)}")
    section_names = [section["name"] for section in runtime_template.get("sections", [])]
    if section_names != ["introduction", "development", "references"]:
        issues.append(f"unexpected runtime template sections: {section_names}")
    reference_section = runtime_template.get("sections", [])[-1]
    if reference_section.get("semantic_role") != "reference_section":
        issues.append("references section was not marked terminal/reference_section")
    log.event("scenario_check", "uploaded continuation split checks completed", sections=section_names)
    return SmokeResult(not issues, issues, {"sections": section_names})


def _make_tiny_pdf(path: Path, marker: str) -> None:
    import fitz

    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Academic PE Mistral OCR smoke document.")
    page.insert_text((72, 96), f"Unique marker: {marker}.")
    doc.save(str(path))
    doc.close()


def check_mistral_ocr_direct(output_dir: Path, log: SmokeLog) -> SmokeResult:
    if not is_secret_configured("mistral"):
        return SmokeResult(False, ["mistral secret is not configured"], {}, blocked=True)

    marker = "APE-OCR-SCENARIO-MARKER-20260616"
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / "mistral_ocr_smoke.pdf"
    _make_tiny_pdf(pdf_path, marker)
    try:
        content = process_file_via_mistral_ocr(pdf_path.name, pdf_path.read_bytes(), "application/pdf")
    finally:
        try:
            pdf_path.unlink()
        except Exception:
            pass
    issues = []
    if not content.strip():
        issues.append("Mistral OCR returned empty content")
    if marker not in content:
        issues.append("Mistral OCR output did not include the unique marker")
    tokens = count_tokens(content)
    log.event("scenario_check", "mistral OCR direct checks completed", tokens=tokens, has_marker=marker in content)
    return SmokeResult(not issues, issues, {"tokens": tokens, "has_marker": marker in content})


def _provider_name(config: AgentConfig) -> str:
    return str(getattr(config.provider, "value", config.provider))


def check_real_llm_web_research(output_dir: Path, log: SmokeLog) -> SmokeResult:
    config = load_config(str(ROOT / "config" / "agents.yaml")).model_copy(deep=True)
    missing = sorted(
        {
            provider
            for name in ("writer", "planner")
            if name in config.agents
            for provider in [_provider_name(config.agents[name])]
            if provider != "mock" and not is_secret_configured(provider)
        }
    )
    if missing:
        return SmokeResult(False, [f"missing provider secret(s): {', '.join(missing)}"], {}, blocked=True)

    output_dir.mkdir(parents=True, exist_ok=True)
    config.dynamic_examples_enabled = False
    config.retry.max_retries = 0
    config.pipeline.output_dir = str(output_dir)
    config.pipeline.template_mode = TemplateMode.custom
    config.pipeline.academic_mode = False
    config.pipeline.sections = [
        SectionPrompt(
            name="brief",
            topic="Current AI-assisted OCR and web research workflow for academic document drafting",
            instruction="Write a concise operational brief with concrete source-aware claims. Keep it under 900 characters.",
        )
    ]
    config.quality_gate.volume.enabled = False
    config.quality_gate.latex.enabled = False
    config.quality_gate.markdown.enabled = False
    for agent_cfg in config.agents.values():
        agent_cfg.self_critique.enabled = False
    config.agents.pop("reviewer", None)

    if "researcher" not in config.agents:
        config.agents["researcher"] = AgentConfig(
            role="Researcher",
            provider="mock",
            model="deterministic-search",
            temperature=0.0,
            agent_type="researcher",
            system_prompt="Deterministic web researcher.",
        )

    snapshot = ", ".join(
        f"{name}={_provider_name(cfg)}/{cfg.model}"
        for name, cfg in config.agents.items()
        if name in {"writer", "planner", "researcher"}
    )
    log.event("real_llm_config", "Loaded bounded real-LLM smoke config", config_snapshot=snapshot)

    orchestrator = create_orchestrator_from_config(
        config,
        user_topic="AI OCR plus web research in document drafting",
        user_instructions=(
            "Keep the topic as is. Use web search findings when planning. "
            "The writer must only write from the planner-curated plan."
        ),
        reference_materials=[
            {
                "filename": "local_policy_note.md",
                "content": "Local policy marker: WRITER_MUST_NOT_SEE_RAW_REFERENCE_MARKER. Planner should use this only as background.",
            }
        ],
        web_search_enabled=True,
    )
    orchestrator.run_pipeline(render_artifact=False)
    plan = orchestrator.context.get("document_plan", "")
    brief = orchestrator.context.get("brief", "")
    issues = []
    if not orchestrator.search_findings.strip():
        issues.append("researcher returned empty search findings")
    if "http" not in plan and "Source" not in plan and "URL" not in plan:
        issues.append("planner plan does not appear source-aware")
    if not brief.strip():
        issues.append("writer produced empty brief")
    if "WRITER_MUST_NOT_SEE_RAW_REFERENCE_MARKER" in brief:
        issues.append("raw reference marker leaked into writer output")

    details = {
        "config_snapshot": snapshot,
        "search_chars": len(orchestrator.search_findings),
        "plan_chars": len(plan),
        "brief_chars": len(brief),
        "plan_preview": " ".join(plan.split())[:500],
        "brief_preview": " ".join(brief.split())[:500],
    }
    log.event("real_llm_result_details", "Collected real-LLM smoke details", **details)
    return SmokeResult(not issues, issues, details)


SCENARIO_RUNNERS: dict[str, Callable[[Path, SmokeLog], SmokeResult]] = {
    "web_search_off_standard_pipeline": check_web_search_off,
    "web_search_on_researcher_boundary": check_web_search_on_boundary,
    "reference_attachment_planner_only": check_reference_attachment_planner_only,
    "uploaded_continuation_source": check_uploaded_continuation_source,
    "mistral_ocr_direct": check_mistral_ocr_direct,
    "real_llm_web_research": check_real_llm_web_research,
}


def write_run_header(note: FlushNote, scenario: SmokeScenario) -> None:
    note.write("")
    note.write(f"## Run {datetime.now().isoformat(timespec='seconds')} - {scenario.scenario_id}")
    note.write("")
    note.write(f"Date: {datetime.now().date().isoformat()}")
    note.write("Commit/branch: local working tree")
    note.write(f"Scenario: {scenario.title} ({scenario.scenario_id})")
    note.write("Expected checks: " + "; ".join(scenario.required_checks))
    note.write("Stage log: see exports/_smoke_ocr_research JSONL log for flushed checkpoints.")


def append_result(note: FlushNote, result: SmokeResult, elapsed: float, log_path: Path) -> None:
    if result.blocked:
        status = "BLOCKED"
    else:
        status = "PASS" if result.passed else "FAIL"
    issue_text = "; ".join(result.issues) if result.issues else "none"
    note.write(f"Result: {status}")
    note.write(f"Elapsed: {elapsed:.1f}s")
    note.write(f"Observed issue: {issue_text}")
    try:
        follow_up = str(log_path.relative_to(ROOT))
    except ValueError:
        follow_up = str(log_path)
    note.write(f"Follow-up: {follow_up}")


def run_scenario(scenario: SmokeScenario, args: argparse.Namespace) -> int:
    note_path = ROOT / args.note
    note = FlushNote(note_path)
    write_run_header(note, scenario)
    output_dir = LOG_DIR / datetime.now().strftime("%Y%m%d_%H%M%S") / scenario.scenario_id
    log_path = Path(args.log_path) if args.log_path else output_dir / "stage_log.jsonl"
    log = SmokeLog(scenario.scenario_id, log_path)
    log.event("scenario_start", "Scenario started")

    started = time.monotonic()
    try:
        result = SCENARIO_RUNNERS[scenario.scenario_id](output_dir, log)
    except Exception as exc:
        result = SmokeResult(False, [f"{exc.__class__.__name__}: {exc}"], {}, blocked=False)
        log.event("scenario_error", "Scenario failed before rubric checks", error=exc.__class__.__name__)
    elapsed = time.monotonic() - started

    log.event(
        "scenario_result",
        "Scenario completed",
        result="BLOCKED" if result.blocked else "PASS" if result.passed else "FAIL",
        issues=result.issues,
        details=result.details,
        elapsed_seconds=round(elapsed, 1),
    )
    append_result(note, result, elapsed, log_path)
    if result.blocked:
        return 2
    return 0 if result.passed else 1


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    scenarios = sorted(scenario_catalog())
    parser = argparse.ArgumentParser(description="Run one OCR/research smoke scenario.")
    parser.add_argument("scenario", choices=scenarios, help="Scenario id to run.")
    parser.add_argument("--note", default=str(NOTE_PATH.relative_to(ROOT)), help="Note path relative to repository root.")
    parser.add_argument("--log-path", default=None, help="Optional JSONL log path.")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    return run_scenario(scenario_catalog()[args.scenario], args)


if __name__ == "__main__":
    raise SystemExit(main())
