from __future__ import annotations

import argparse
import contextlib
import json
import logging
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from academic_pe.core.config import AppConfig, SectionPrompt, TemplateMode, load_config
from academic_pe.core.orchestrator import PipelineState, create_orchestrator_from_config
from academic_pe.core.secrets import is_secret_configured

NOTE_PATH = ROOT / "dev_docs" / "CONTINUATION_REAL_SMOKE_NOTES.md"
LOG_DIR = ROOT / "exports" / "_smoke"


@dataclass(frozen=True)
class SmokeScenario:
    scenario_id: str
    title: str
    topic: str
    instructions: str
    continuation_source: Dict[str, Any]
    required_checks: tuple[str, ...]


def scenario_catalog() -> Dict[str, SmokeScenario]:
    return {
        "creative_continuation": SmokeScenario(
            scenario_id="creative_continuation",
            title="Creative continuation",
            topic="Continue",
            instructions="",
            continuation_source={
                "source_type": "generated",
                "topic": "The Lantern Under the Ice",
                "instructions": "A quiet, atmospheric short story in three visible parts.",
                "context": {
                    "opening": (
                        "## Opening\n\nMara kept the brass lantern wrapped in a scarf so its glass would not sing "
                        "against the sled rails. The town behind her had gone silent under blue winter dusk."
                    ),
                    "descent": (
                        "## Descent\n\nAt the old quarry, the ice answered every step with a low, patient note. "
                        "Mara lowered the lantern into a black seam and saw a staircase glimmer below."
                    ),
                    "disappearance": (
                        "## Disappearance\n\nShe tied the rope around her waist and stepped down until the surface "
                        "became a pale coin overhead. Somewhere under the ice, someone breathed her name."
                    ),
                },
            },
            required_checks=(
                "same story rather than restart",
                "no visible exposition/development/red flags headings",
                "source part style preserved",
                "continuation intent and merge metadata present",
            ),
        ),
        "creative_bridge": SmokeScenario(
            scenario_id="creative_bridge",
            title="Creative bridge",
            topic="Continue",
            instructions="",
            continuation_source={
                "source_type": "generated",
                "topic": "The Last Train Home",
                "instructions": "A restrained literary scene with a closed ending.",
                "context": {
                    "story": (
                        "## Platform\n\nThe last train sighed into the station after midnight. Lena gave the conductor "
                        "the ticket she had carried for seven years.\n\n## Homecoming\n\nAt dawn she reached the "
                        "house by the river, unlocked the blue door, and found the table set for two. She smiled, "
                        "closed the door behind her, and knew the waiting was over. The end."
                    )
                },
            },
            required_checks=(
                "closed ending bridged or tail replaced",
                "no disconnected branch after hard ending",
                "no visible internal planning labels",
                "merge metadata reflects bridge/append behavior",
            ),
        ),
        "school_revision": SmokeScenario(
            scenario_id="school_revision",
            title="School revision",
            topic="My Favorite City",
            instructions="Improve this school composition in place. Keep a student voice and do not add a new essay.",
            continuation_source={
                "source_type": "generated",
                "topic": "My Favorite City",
                "instructions": "Middle-school English composition.",
                "context": {
                    "essay": (
                        "My favorite city is Saint Petersburg. It has many beautiful streets and bridges. "
                        "I went there with my family and liked the museums. The weather was rainy, but it was "
                        "interesting. In conclusion, I want to visit this city again."
                    )
                },
            },
            required_checks=(
                "revises in place instead of appending",
                "student-level register preserved",
                "no duplicate essay/introduction/conclusion",
                "intent is revise_in_place",
            ),
        ),
        "academic_references": SmokeScenario(
            scenario_id="academic_references",
            title="Academic/RGR continuation with references",
            topic="Add the next analysis section",
            instructions=(
                "Continue the RGR-style document with a short next analysis section. Keep references terminal "
                "and merge any new source into the same bibliography if needed."
            ),
            continuation_source={
                "source_type": "generated",
                "topic": "Queueing Model for a Helpdesk System",
                "instructions": "Structured RGR report with formulas and references.",
                "context": {
                    "introduction": (
                        "The report estimates a simple helpdesk queue using arrival rate "
                        "$\\lambda$ and service rate $\\mu$."
                    ),
                    "calculation": (
                        "For an M/M/1 queue, utilization is $\\rho = \\lambda / \\mu$. "
                        "The system is stable when $\\rho < 1$."
                    ),
                    "references": (
                        "1. Kleinrock, L. Queueing Systems. Volume 1: Theory. Wiley, 1975. "
                        "Classic reference for M/M/1 queue notation, stability conditions, and performance measures."
                    ),
                },
            },
            required_checks=(
                "new body appears before references",
                "references remain terminal",
                "bibliography is a single merged section",
                "no editorial 'new sources added' label",
            ),
        ),
        "technical_continuation": SmokeScenario(
            scenario_id="technical_continuation",
            title="Technical document continuation",
            topic="Continue the README",
            instructions="Add the next practical usage section without turning it into an academic paper.",
            continuation_source={
                "source_type": "generated",
                "topic": "README for a CSV validation CLI",
                "instructions": "Practical README with concise headings.",
                "context": {
                    "readme": (
                        "# csv-check\n\n## Install\n\n`pip install csv-check`\n\n## Quick Start\n\n"
                        "Run `csv-check data.csv --schema schema.yml` to validate a file and print errors."
                    )
                },
            },
            required_checks=(
                "README heading style preserved",
                "no forced academic-paper structure",
                "practical usage content appended",
                "no visible internal planning labels",
            ),
        ),
    }


class FlushNote:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, line: str = "") -> None:
        with self.path.open("a", encoding="utf-8") as file:
            file.write(line + "\n")
            file.flush()


class SmokeLogger:
    def __init__(self, scenario_id: str, note: FlushNote, log_path: Path):
        self.scenario_id = scenario_id
        self.note = note
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.events: list[dict[str, Any]] = []

    def event(self, kind: str, message: str, **data: Any) -> None:
        record = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "scenario": self.scenario_id,
            "kind": kind,
            "message": message,
            **{key: value for key, value in data.items() if value is not None},
        }
        text = json.dumps(record, ensure_ascii=False)
        with self._lock:
            self.events.append(record)
            with self.log_path.open("a", encoding="utf-8") as file:
                file.write(text + "\n")
                file.flush()
            try:
                print(text, flush=True)
            except OSError:
                # Parent process output may be closed by an external timeout while
                # the child is still unwinding. The JSONL file is the source of truth.
                pass


class Heartbeat:
    def __init__(self, emit: Callable[[str], None], interval_seconds: float):
        self.emit = emit
        self.interval_seconds = interval_seconds
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def __enter__(self) -> "Heartbeat":
        if self.interval_seconds <= 0:
            return self
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1)

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            self.emit("heartbeat")


def config_snapshot(config: AppConfig) -> str:
    parts = []
    for name in ("writer", "reviewer", "planner", "example_generator"):
        agent = config.agents.get(name)
        if agent is None:
            continue
        provider = getattr(agent.provider, "value", agent.provider)
        parts.append(f"{name}={provider}/{agent.model}")
    return ", ".join(parts)


def configured_real_providers(config: AppConfig) -> list[str]:
    providers = []
    for agent in config.agents.values():
        provider = str(getattr(agent.provider, "value", agent.provider))
        if provider != "mock" and provider not in providers:
            providers.append(provider)
    return providers


def safe_config_for_smoke(config: AppConfig, output_dir: Path) -> AppConfig:
    smoke_config = config.model_copy(deep=True)
    smoke_config.dynamic_examples_enabled = False
    smoke_config.pipeline.output_dir = str(output_dir)
    smoke_config.pipeline.template_mode = TemplateMode.custom
    smoke_config.pipeline.academic_mode = False
    smoke_config.quality_gate.volume.min_chars = min(smoke_config.quality_gate.volume.min_chars, 80)
    smoke_config.retry.max_retries = min(smoke_config.retry.max_retries, 1)
    return smoke_config


def align_config_sections_to_continuation_source(config: AppConfig, scenario: SmokeScenario) -> AppConfig:
    smoke_config = config.model_copy(deep=True)
    context = scenario.continuation_source.get("context")
    if not isinstance(context, dict):
        return smoke_config

    sections = []
    for name, content in context.items():
        if name == "document_plan" or not str(content or "").strip():
            continue
        sections.append(
            SectionPrompt(
                name=name,
                topic=name.replace("_", " ").replace("-", " ").title(),
                instruction=(
                    "Continue or edit this existing source section according to the scenario. "
                    "Preserve the source genre, heading style, terminology, and audience level."
                ),
            )
        )

    if sections:
        smoke_config.pipeline.sections = sections
        smoke_config.pipeline.template_mode = TemplateMode.custom
    return smoke_config


def disable_expensive_smoke_loops(config: AppConfig) -> AppConfig:
    smoke_config = config.model_copy(deep=True)
    for agent in smoke_config.agents.values():
        agent.self_critique.enabled = False
    smoke_config.retry.max_retries = 0
    return smoke_config


@contextlib.contextmanager
def instrument_llm_calls(smoke_log: SmokeLogger, heartbeat_seconds: float):
    import academic_pe.agents.base as base_module
    import academic_pe.agents.prompt_enhancer as prompt_enhancer_module
    import academic_pe.agents.self_critique as self_critique_module
    import academic_pe.agents.writer as writer_module
    import academic_pe.core.llm as llm_module
    import academic_pe.core.planner_agent as planner_module

    original = llm_module._call_provider_generate

    call_stack = threading.local()

    def infer_call_stage(user_prompt: str) -> str:
        text = (user_prompt or "").lower()
        if "refine the document topic" in text:
            return "topic_refinement"
        if "repair the draft in one pass" in text:
            return "self_critique"
        if "create a document plan" in text or "document plan" in text:
            return "planning"
        if "produce merge-operation payloads" in text:
            return "merge_operation_payload"
        if "check the provided text" in text:
            return "review"
        if "minimal patch" in text and "replace blocks" in text:
            return "patch_revision"
        if "verify if the text" in text:
            return "self_verification"
        if "write the section" in text or "draft" in text:
            return "drafting"
        return "agent_call"

    def wrapped(provider, system_prompt, user_prompt, model, temperature, on_delta=None):
        provider_name = provider.__class__.__name__
        started = time.monotonic()
        stage = infer_call_stage(user_prompt)
        depth = getattr(call_stack, "depth", 0)
        call_stack.depth = depth + 1
        smoke_log.event(
            "agent_call_start",
            "LLM call started",
            provider=provider_name,
            model=model,
            temperature=temperature,
            stage=stage,
            nested_depth=depth,
        )
        try:
            with Heartbeat(
                lambda kind: smoke_log.event(
                    kind,
                    "LLM call still running",
                    provider=provider_name,
                    model=model,
                    stage=stage,
                    elapsed_seconds=round(time.monotonic() - started, 1),
                ),
                heartbeat_seconds,
            ):
                result = original(provider, system_prompt, user_prompt, model, temperature, on_delta=on_delta)
        except Exception as exc:
            smoke_log.event(
                "agent_call_error",
                "LLM call failed",
                provider=provider_name,
                model=model,
                stage=stage,
                elapsed_seconds=round(time.monotonic() - started, 1),
                error=exc.__class__.__name__,
                error_message=safe_error_message(exc),
            )
            raise
        finally:
            call_stack.depth = depth
        smoke_log.event(
            "agent_call_end",
            "LLM call finished",
            provider=provider_name,
            model=model,
            stage=stage,
            nested_depth=depth,
            elapsed_seconds=round(time.monotonic() - started, 1),
            output_chars=len(result or ""),
        )
        return result

    modules = [
        llm_module,
        base_module,
        writer_module,
        self_critique_module,
        prompt_enhancer_module,
        planner_module,
    ]
    previous = {module: getattr(module, "_call_provider_generate", None) for module in modules}
    original_reviewer_process = writer_module.ReviewerAgent.process

    def reviewer_process(self, task_description, context=None, on_delta=None, document_sections=None):
        started = time.monotonic()
        provider_name = self.llm.__class__.__name__
        smoke_log.event(
            "agent_call_start",
            "Reviewer call started",
            provider=provider_name,
            model=self.config.model,
            temperature=self.config.temperature,
            stage="review",
            nested_depth=0,
        )
        try:
            result = original_reviewer_process(
                self,
                task_description,
                context=context,
                on_delta=on_delta,
                document_sections=document_sections,
            )
        except Exception as exc:
            smoke_log.event(
                "agent_call_error",
                "Reviewer call failed",
                provider=provider_name,
                model=self.config.model,
                stage="review",
                elapsed_seconds=round(time.monotonic() - started, 1),
                error=exc.__class__.__name__,
                error_message=safe_error_message(exc),
            )
            raise
        smoke_log.event(
            "agent_call_end",
            "Reviewer call finished",
            provider=provider_name,
            model=self.config.model,
            stage="review",
            nested_depth=0,
            elapsed_seconds=round(time.monotonic() - started, 1),
            output_chars=len(result or ""),
        )
        return result

    try:
        for module in modules:
            if hasattr(module, "_call_provider_generate"):
                setattr(module, "_call_provider_generate", wrapped)
        writer_module.ReviewerAgent.process = reviewer_process
        yield
    finally:
        for module, value in previous.items():
            if value is not None:
                setattr(module, "_call_provider_generate", value)
        writer_module.ReviewerAgent.process = original_reviewer_process


class StageLogHandler(logging.Handler):
    def __init__(self, smoke_log: SmokeLogger):
        super().__init__(level=logging.INFO)
        self.smoke_log = smoke_log

    def emit(self, record: logging.LogRecord) -> None:
        message = safe_stage_message(record.getMessage())
        lower = message.lower()
        if (
            "state:" in lower
            or "pipeline" in lower
            or "reviewer" in lower
            or "quality gate" in lower
            or "merge flow" in lower
            or "drafting" in lower
            or "creating document plan" in lower
        ):
            self.smoke_log.event("stage_log", message, logger=record.name, level=record.levelname)


def safe_stage_message(message: str, max_chars: int = 260) -> str:
    sanitized = " ".join((message or "").split())
    lower = sanitized.lower()
    redaction_triggers = (
        "raw preview:",
        "reviewer rejected",
        "generated section",
        "system prompt used:",
    )
    if any(trigger in lower for trigger in redaction_triggers):
        prefix = sanitized.split(":", 1)[0] if ":" in sanitized else sanitized[:80]
        sanitized = f"{prefix}: [content redacted; see pass/fail summary and pipeline state metadata]"
    if len(sanitized) <= max_chars:
        return sanitized
    return sanitized[: max_chars - 3].rstrip() + "..."


def safe_error_message(exc: BaseException, max_chars: int = 180) -> str:
    text = " ".join(str(exc).split())
    if not text:
        return ""
    lowered = text.lower()
    if "api_key" in lowered or "authorization" in lowered or "bearer " in lowered:
        return "[redacted]"
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


@contextlib.contextmanager
def capture_stage_logs(smoke_log: SmokeLogger):
    handler = StageLogHandler(smoke_log)
    root_logger = logging.getLogger()
    previous_level = root_logger.level
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)
    try:
        yield
    finally:
        root_logger.removeHandler(handler)
        root_logger.setLevel(previous_level)


def final_text(context: Dict[str, str]) -> str:
    return "\n\n".join(value for key, value in context.items() if key != "document_plan")


def run_checks(
    scenario: SmokeScenario,
    context: Dict[str, str],
    metadata: Dict[str, Any],
    events: Optional[list[dict[str, Any]]] = None,
) -> tuple[bool, list[str]]:
    text = final_text(context)
    lower = text.lower()
    issues: list[str] = []

    forbidden_labels = ("exposition", "development", "red flags", "conflict analysis", "pacing notes")
    for label in forbidden_labels:
        if f"## {label}" in lower or f"# {label}" in lower:
            issues.append(f"visible internal planning label: {label}")

    if scenario.scenario_id == "academic_references":
        references_index = lower.rfind("references")
        if references_index >= 0:
            after_refs = lower[references_index + len("references") :].strip()
            if "##" in after_refs or "# " in after_refs:
                issues.append("body-like heading appears after references")
        if sum(1 for line in text.splitlines() if line.strip().lower().lstrip("# ").startswith("references")) > 1:
            issues.append("multiple visible references headings detected")

    if scenario.scenario_id == "school_revision" and metadata.get("continuation_intent", {}).get("intent") != "revise_in_place":
        issues.append("intent metadata is not revise_in_place")

    if scenario.scenario_id == "technical_continuation" and any(term in lower for term in ("abstract", "methodology", "literature review")):
        issues.append("technical continuation drifted into academic-paper structure")

    if not metadata.get("continuation_intent"):
        issues.append("missing continuation_intent metadata")
    if not metadata.get("edit_plan"):
        issues.append("missing edit_plan metadata")

    if len(text.strip()) < 200:
        issues.append("final text is unexpectedly short")

    stage_messages = [
        str(event.get("message") or "")
        for event in (events or [])
        if event.get("kind") == "stage_log"
    ]
    if any("Reviewer rejected (attempt 3/3)" in message for message in stage_messages):
        issues.append("reviewer rejected the final retry but pipeline proceeded to DONE")
    if any("Max retries reached" in message for message in stage_messages):
        issues.append("review loop exhausted retries")

    return not issues, issues


def write_run_header(note: FlushNote, scenario: SmokeScenario, config: AppConfig) -> None:
    note.write("")
    note.write(f"## Run {datetime.now().isoformat(timespec='seconds')} - {scenario.scenario_id}")
    note.write("")
    note.write(f"Date: {datetime.now().date().isoformat()}")
    note.write("Commit/branch: local working tree")
    note.write(f"Config snapshot: {config_snapshot(config)}")
    note.write(f"Scenario: {scenario.title} ({scenario.scenario_id})")
    note.write("Expected checks: " + "; ".join(scenario.required_checks))
    note.write("Stage log: see exports/_smoke JSONL log for full flushed checkpoints.")


def append_result(
    note: FlushNote,
    *,
    passed: bool,
    elapsed: float,
    issues: Iterable[str],
    log_path: Path,
    blocked: bool = False,
) -> None:
    if blocked:
        result = "BLOCKED"
    else:
        result = "PASS" if passed else "FAIL"
    issue_text = "; ".join(issues) if issues else "none"
    note.write(f"Result: {result}")
    note.write(f"Elapsed: {elapsed:.1f}s")
    note.write(f"Observed imbalance: {issue_text}")
    try:
        follow_up = str(log_path.relative_to(ROOT))
    except ValueError:
        follow_up = str(log_path)
    note.write(f"Follow-up: {follow_up}")


def run_scenario(scenario: SmokeScenario, args: argparse.Namespace) -> int:
    config = load_config(str(ROOT / args.config))
    note = FlushNote(ROOT / args.note)
    write_run_header(note, scenario, config)

    real_providers = configured_real_providers(config)
    missing = [provider for provider in real_providers if not is_secret_configured(provider)]
    if missing and not args.allow_mock:
        append_result(
            note,
            passed=False,
            blocked=True,
            elapsed=0.0,
            issues=[f"missing configured real provider secret(s): {', '.join(missing)}"],
            log_path=Path(args.log_path) if args.log_path else LOG_DIR,
        )
        print(f"Blocked: missing configured provider secrets: {', '.join(missing)}", flush=True)
        return 2

    output_dir = LOG_DIR / datetime.now().strftime("%Y%m%d_%H%M%S") / scenario.scenario_id
    log_path = Path(args.log_path) if args.log_path else output_dir / "stage_log.jsonl"
    smoke_log = SmokeLogger(scenario.scenario_id, note, log_path)
    smoke_config = safe_config_for_smoke(config, output_dir)
    smoke_config = align_config_sections_to_continuation_source(smoke_config, scenario)
    if args.disable_expensive_loops:
        smoke_config = disable_expensive_smoke_loops(smoke_config)

    started = time.monotonic()
    smoke_log.event("scenario_start", "Scenario started", config_snapshot=config_snapshot(config))
    try:
        with instrument_llm_calls(smoke_log, args.heartbeat_seconds), capture_stage_logs(smoke_log):
            orchestrator = create_orchestrator_from_config(
                smoke_config,
                user_topic=scenario.topic,
                user_instructions=scenario.instructions,
                continuation_source=scenario.continuation_source,
            )

            def on_enter(old: PipelineState, new: PipelineState) -> None:
                smoke_log.event("stage_transition", "Pipeline state entered", old_state=old.name, new_state=new.name)

            def on_exit(old: PipelineState, new: PipelineState) -> None:
                smoke_log.event("stage_transition", "Pipeline state exited", old_state=old.name, new_state=new.name)

            orchestrator.on_enter(on_enter)
            orchestrator.on_exit(on_exit)
            orchestrator.run_pipeline(render_artifact=False)
    except Exception as exc:
        elapsed = time.monotonic() - started
        smoke_log.event(
            "scenario_error",
            "Scenario failed before rubric checks",
            elapsed_seconds=round(elapsed, 1),
            error=exc.__class__.__name__,
        )
        append_result(
            note,
            passed=False,
            elapsed=elapsed,
            issues=[f"{exc.__class__.__name__}: {exc}"],
            log_path=log_path,
        )
        return 1

    elapsed = time.monotonic() - started
    metadata = orchestrator._runtime_metadata()
    passed, issues = run_checks(scenario, orchestrator.context, metadata, smoke_log.events)
    smoke_log.event(
        "scenario_result",
        "Scenario rubric completed",
        elapsed_seconds=round(elapsed, 1),
        result="PASS" if passed else "FAIL",
        issues=issues,
    )
    append_result(note, passed=passed, elapsed=elapsed, issues=issues, log_path=log_path)
    return 0 if passed else 1


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    scenarios = sorted(scenario_catalog())
    parser = argparse.ArgumentParser(
        description="Run exactly one continuation real-provider smoke scenario with flushed progress logging."
    )
    parser.add_argument("scenario", choices=scenarios, help="Scenario id to run.")
    parser.add_argument("--config", default="config/agents.yaml", help="Config path relative to repository root.")
    parser.add_argument("--note", default=str(NOTE_PATH.relative_to(ROOT)), help="Note path relative to repository root.")
    parser.add_argument("--log-path", default=None, help="Optional JSONL log path.")
    parser.add_argument("--heartbeat-seconds", type=float, default=20.0, help="Heartbeat interval around long LLM calls.")
    parser.add_argument("--allow-mock", action="store_true", help="Allow runs when config uses mock/no real secrets.")
    parser.add_argument(
        "--disable-expensive-loops",
        action="store_true",
        help="Diagnostic mode: disable self-critique and provider retry wrappers for this smoke run.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    scenario = scenario_catalog()[args.scenario]
    return run_scenario(scenario, args)


if __name__ == "__main__":
    raise SystemExit(main())
