from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from academic_pe.core.config import (
    AgentConfig,
    SectionPrompt,
    TemplateMode,
    load_config,
)
from academic_pe.core.orchestrator import create_orchestrator_from_config
from academic_pe.core.secrets import is_secret_configured

NOTE_PATH = ROOT / "dev_docs" / "OCR_RESEARCH_QUALITY_EVAL.md"
OUTPUT_DIR = ROOT / "exports" / "_quality_ocr_research"


@dataclass(frozen=True)
class QualityScenario:
    scenario_id: str
    title: str
    topic: str
    instructions: str
    section: SectionPrompt
    web_search_enabled: bool = False
    reference_materials: tuple[dict[str, str], ...] = ()
    continuation_source: Optional[dict[str, Any]] = None
    rubric: tuple[str, ...] = ()


def scenario_catalog() -> dict[str, QualityScenario]:
    return {
        "web_research_operational_brief": QualityScenario(
            scenario_id="web_research_operational_brief",
            title="Source-aware operational brief",
            topic="AI OCR and web research workflow for academic document drafting",
            instructions=(
                "Use current web context during planning. Produce a concise operational brief. "
                "Do not mention internal pipeline mechanics unless they are user-facing workflow steps. "
                "Do not add a References section; keep source awareness inline or as a short source note."
            ),
            section=SectionPrompt(
                name="brief",
                topic="AI OCR and web research workflow for academic document drafting",
                instruction=(
                    "Write a clear operational brief with source-aware claims, practical workflow steps, "
                    "and one limitation. Keep it reasonably compact; do not optimize for an exact character count. "
                    "Do not use academic headings such as References, Literature Review, or Methodology."
                ),
            ),
            web_search_enabled=True,
            reference_materials=(
                {
                    "filename": "local_policy_note.md",
                    "content": (
                        "Planner-only note: raw marker QUALITY_RAW_REFERENCE_MARKER must not appear in final prose. "
                        "Use only as a reminder that Writer should receive curated context."
                    ),
                },
            ),
            rubric=(
                "uses current/source-aware context without fabricating unsupported certainty",
                "reads as a coherent user-facing brief rather than a plan dump",
                "includes practical workflow steps and at least one limitation",
                "does not leak QUALITY_RAW_REFERENCE_MARKER",
                "does not expose internal labels such as red_flags, exposition, or development notes",
            ),
        ),
        "uploaded_continuation_micro_report": QualityScenario(
            scenario_id="uploaded_continuation_micro_report",
            title="Uploaded continuation micro-report",
            topic="Continue the uploaded mini-report with a short recommendations section",
            instructions=(
                "Continue the existing report without restarting it. Preserve the existing formal report style "
                "and add practical recommendations before the references."
            ),
            section=SectionPrompt(
                name="recommendations",
                topic="Recommendations continuing the existing mini-report",
                instruction=(
                    "Write the continuation recommendations as part of the same report. "
                    "Avoid a new introduction and do not duplicate the references section."
                ),
            ),
            continuation_source={
                "source_type": "uploaded",
                "topic": "Mini-report on OCR quality control",
                "instructions": "Formal mini-report style.",
                "context": {
                    "overview": (
                        "OCR quality control depends on comparing extracted text with source layout, "
                        "checking headings and tables, and flagging low-confidence sections for review."
                    ),
                    "findings": (
                        "The strongest results appear when OCR output is normalized before LLM processing. "
                        "Human review remains important for scanned documents with mixed layouts."
                    ),
                    "references": "1. Internal OCR QA checklist.\n2. Document AI deployment notes.",
                },
                "runtime_template": {
                    "sections": [
                        {"name": "overview", "title": "Overview", "semantic_role": "body"},
                        {"name": "findings", "title": "Findings", "semantic_role": "body"},
                        {"name": "references", "title": "References", "semantic_role": "reference_section"},
                    ]
                },
                "template_mode": "custom",
            },
            rubric=(
                "continues the existing report instead of restarting with a new introduction",
                "preserves formal report style",
                "adds useful recommendations",
                "does not duplicate references or place new body content after references",
                "does not expose internal continuation/planning labels",
            ),
        ),
    }


def _provider_name(config: AgentConfig) -> str:
    return str(getattr(config.provider, "value", config.provider))


def _prepare_config(scenario: QualityScenario, output_dir: Path):
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
        raise RuntimeError(f"missing provider secret(s): {', '.join(missing)}")

    config.dynamic_examples_enabled = False
    config.retry.max_retries = 0
    config.pipeline.output_dir = str(output_dir)
    config.pipeline.template_mode = TemplateMode.custom
    config.pipeline.academic_mode = False
    config.pipeline.sections = [scenario.section]
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
    return config


def _append_note(text: str) -> None:
    NOTE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with NOTE_PATH.open("a", encoding="utf-8") as f:
        f.write(text)
        if not text.endswith("\n"):
            f.write("\n")


def _strip_duplicate_heading(content: str, title: str) -> str:
    lines = str(content or "").splitlines()
    if not lines:
        return ""
    first = lines[0].strip()
    if first.startswith("#") and first.lstrip("#").strip().lower() == title.strip().lower():
        return "\n".join(lines[1:]).strip()
    return str(content)


def run_scenario(scenario: QualityScenario) -> int:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = OUTPUT_DIR / stamp / scenario.scenario_id
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    config = _prepare_config(scenario, output_dir)
    snapshot = ", ".join(
        f"{name}={_provider_name(cfg)}/{cfg.model}"
        for name, cfg in config.agents.items()
        if name in {"writer", "planner", "researcher"}
    )

    orchestrator = create_orchestrator_from_config(
        config,
        user_topic=scenario.topic,
        user_instructions=scenario.instructions,
        continuation_source=scenario.continuation_source,
        reference_materials=list(scenario.reference_materials),
        web_search_enabled=scenario.web_search_enabled,
    )
    error = ""
    exit_code = 0
    try:
        orchestrator.run_pipeline(render_artifact=False)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        exit_code = 1
    elapsed = time.monotonic() - started

    plan = orchestrator.context.get("document_plan", "")
    body = orchestrator.context.get(scenario.section.name, "")
    section_titles = {
        section.name: getattr(section, "topic", None) or getattr(section, "title", None) or section.name
        for section in orchestrator._config.pipeline.sections
    }
    assembled_output = "\n\n".join(
        f"## {section_titles.get(name, name)}\n{_strip_duplicate_heading(str(content), section_titles.get(name, name))}"
        for name, content in orchestrator.context.items()
        if name != "document_plan" and str(content).strip()
    )
    if not body and assembled_output:
        body = assembled_output
    payload = {
        "scenario": scenario.scenario_id,
        "title": scenario.title,
        "elapsed_seconds": round(elapsed, 1),
        "config_snapshot": snapshot,
        "rubric": list(scenario.rubric),
        "search_findings_chars": len(orchestrator.search_findings),
        "error": error,
        "document_plan": plan,
        "output": body,
        "assembled_output": assembled_output,
        "all_context_keys": sorted(orchestrator.context),
    }
    json_path = output_dir / "result.json"
    md_path = output_dir / "result.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                f"# {scenario.title}",
                "",
                f"Scenario: `{scenario.scenario_id}`",
                f"Elapsed: {elapsed:.1f}s",
                f"Config: {snapshot}",
                f"Search findings chars: {len(orchestrator.search_findings)}",
                *(["", "## Error", error] if error else []),
                "",
                "## Rubric",
                *[f"- [ ] {item}" for item in scenario.rubric],
                "",
                "## Document Plan",
                plan,
                "",
                "## Output",
                body,
                "",
            ]
        ),
        encoding="utf-8",
    )

    _append_note(
        "\n".join(
            [
                "",
                f"## Run {datetime.now().isoformat(timespec='seconds')} - {scenario.scenario_id}",
                "",
                f"Result: PENDING MANUAL REVIEW",
                *(["Pipeline error: `" + error.replace("`", "'") + "`"] if error else []),
                f"Elapsed: {elapsed:.1f}s",
                f"Config snapshot: {snapshot}",
                f"Output: `{md_path.relative_to(ROOT)}`",
                f"JSON: `{json_path.relative_to(ROOT)}`",
                "",
            ]
        )
    )
    print(f"Wrote {md_path}")
    return exit_code


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    scenarios = sorted(scenario_catalog())
    parser = argparse.ArgumentParser(description="Run one semi-manual OCR/research quality evaluation scenario.")
    parser.add_argument("scenario", choices=scenarios)
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    return run_scenario(scenario_catalog()[args.scenario])


if __name__ == "__main__":
    raise SystemExit(main())
