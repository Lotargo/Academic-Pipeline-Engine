from __future__ import annotations

import logging
import os
import signal
from enum import Enum, auto
from typing import Callable, Dict, List, Optional, Protocol

from academic_pe.core.config import AppConfig, load_config
from academic_pe.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class PipelineState(Enum):
    INIT = auto()
    DRAFTING = auto()
    REVIEWING = auto()
    RENDERING = auto()
    DONE = auto()
    FAILED = auto()


_DEFAULT_TRANSITIONS: Dict[PipelineState, List[PipelineState]] = {
    PipelineState.INIT: [PipelineState.DRAFTING],
    PipelineState.DRAFTING: [PipelineState.REVIEWING],
    PipelineState.REVIEWING: [PipelineState.DRAFTING, PipelineState.RENDERING],
    PipelineState.RENDERING: [PipelineState.DONE],
    PipelineState.DONE: [],
    PipelineState.FAILED: [],
}


class InvalidTransitionError(Exception):
    pass


class PipelineError(Exception):
    pass


class Renderer(Protocol):
    def __call__(
        self,
        content: Dict[str, str],
        output_filename: str,
        config: Optional[AppConfig] = None,
    ) -> str:
        ...


HookFn = Callable[[PipelineState, PipelineState], None]


class Orchestrator:
    def __init__(
        self,
        writer: BaseAgent,
        config: AppConfig,
        reviewer: Optional[BaseAgent] = None,
        renderer: Optional[Renderer] = None,
    ):
        self._writer = writer
        self._reviewer = reviewer
        self._renderer = renderer
        self._config = config
        self._state: PipelineState = PipelineState.INIT
        self.context: Dict[str, str] = {}
        self._state_history: List[PipelineState] = []
        self._hooks: Dict[str, List[HookFn]] = {
            "on_enter": [],
            "on_exit": [],
        }
        self._transitions: Dict[PipelineState, List[PipelineState]] = dict(_DEFAULT_TRANSITIONS)

    @property
    def state(self) -> PipelineState:
        return self._state

    @property
    def previous_state(self) -> Optional[PipelineState]:
        return self._state_history[-1] if self._state_history else None

    def on_enter(self, callback: HookFn) -> None:
        self._hooks["on_enter"].append(callback)

    def on_exit(self, callback: HookFn) -> None:
        self._hooks["on_exit"].append(callback)

    def transition_to(self, new_state: PipelineState) -> None:
        allowed = self._transitions.get(self._state, [])
        if new_state not in allowed:
            raise InvalidTransitionError(
                f"Cannot transition from {self._state.name} to {new_state.name}. "
                f"Allowed: {[s.name for s in allowed]}"
            )
        old_state = self._state
        for hook in self._hooks["on_exit"]:
            hook(old_state, new_state)
        logger.info("State: %s -> %s", old_state.name, new_state.name)
        self._state_history.append(old_state)
        self._state = new_state
        for hook in self._hooks["on_enter"]:
            hook(old_state, new_state)

    def revert(self) -> PipelineState:
        if not self._state_history:
            raise PipelineError("No previous state to revert to.")
        prev = self._state_history.pop()
        logger.info("Revert: %s -> %s", self._state.name, prev.name)
        self._state = prev
        return prev

    def run_pipeline(self) -> str:
        logger.info("Pipeline started.")
        output_path = "(no output)"

        try:
            # --- DRAFTING ---
            self.transition_to(PipelineState.DRAFTING)
            for section in self._config.pipeline.sections:
                task = f"Write a chapter about {section.topic}. {section.instruction}"
                logger.debug("Drafting section: %s", section.name)
                self.context[section.name] = self._writer.process(task)

            # --- REVIEWING ---
            self.transition_to(PipelineState.REVIEWING)

            from academic_pe.agents.writer import ReviewerAgent

            max_retries = 3
            for attempt in range(max_retries):
                if self._reviewer is None:
                    logger.info("No reviewer configured, skipping review.")
                    break

                full_text = "\n\n".join(
                    self.context.get(s.name, "") for s in self._config.pipeline.sections
                )
                critique = self._reviewer.process(
                    "Check the provided text for academic tone and formatting errors. "
                    "Return exactly one line: APPROVED if the text passes, "
                    "or REJECTED followed by a brief reason.",
                    context=full_text,
                )

                approved = (
                    self._reviewer.is_approved(critique)
                    if isinstance(self._reviewer, ReviewerAgent)
                    else critique.strip().upper().startswith("APPROVED")
                )
                if approved:
                    logger.info("Reviewer approved the content.")
                    break

                reason = (
                    self._reviewer.parse_reason(critique)
                    if isinstance(self._reviewer, ReviewerAgent)
                    else critique
                )
                logger.warning("Reviewer rejected (attempt %d/%d): %s", attempt + 1, max_retries, reason[:100])

                if attempt < max_retries - 1:
                    logger.info("Returning to DRAFTING for revision...")
                    self.transition_to(PipelineState.DRAFTING)
                    for section in self._config.pipeline.sections:
                        task = (
                            f"Revise the chapter about {section.topic}. "
                            f"Address these issues: {reason[:500]}. "
                            f"{section.instruction}"
                        )
                        self.context[section.name] = self._writer.process(task)
                    self.transition_to(PipelineState.REVIEWING)
                else:
                    logger.error("Max retries reached. Proceeding to rendering with current content.")

            # --- QUALITY GATE ---
            from academic_pe.core.quality_gate import run_all as run_quality_gate
            qg_result = run_quality_gate(self.context, self._config.quality_gate)
            if not qg_result.passed:
                for issue in qg_result.issues:
                    logger.warning("Quality Gate: %s", issue)
                raise PipelineError(
                    f"Quality Gate failed with {len(qg_result.issues)} issue(s). "
                    + "; ".join(qg_result.issues)
                )
            logger.info("Quality Gate: all checks passed.")

            # --- RENDERING ---
            self.transition_to(PipelineState.RENDERING)

            output_filename = self._config.pipeline.output_filename
            output_dir = self._config.pipeline.output_dir
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, output_filename)

            if self._renderer is not None:
                import inspect
                sig = inspect.signature(self._renderer)
                if "config" in sig.parameters:
                    output_path = self._renderer(self.context, output_filename=output_path, config=self._config)
                else:
                    output_path = self._renderer(self.context, output_filename=output_path)
            else:
                output_path = "(no renderer configured)"
                logger.warning("No renderer configured, skipping DOCX generation.")

            # --- DONE ---
            self.transition_to(PipelineState.DONE)
            logger.info("Pipeline finished. Artifact: %s", output_path)

        except PipelineError:
            raise
        except Exception:
            logger.exception("Pipeline failed at state %s", self._state.name)
            self._state = PipelineState.FAILED
            raise PipelineError(
                f"Pipeline failed at {self._state.name}. Check logs for details."
            ) from None

        return output_path


def create_orchestrator(
    config_path: str = "config/agents.yaml",
    renderer: Optional[Renderer] = None,
) -> Orchestrator:
    config = load_config(config_path)

    writer_cfg = config.agents.get("writer")
    if not writer_cfg:
        raise ValueError("Writer agent configuration is missing")

    from academic_pe.agents.factory import create_agent

    writer = create_agent("writer", writer_cfg, retry_cfg=config.retry)
    reviewer = None
    if "reviewer" in config.agents:
        reviewer = create_agent("reviewer", config.agents["reviewer"], retry_cfg=config.retry)

    return Orchestrator(
        writer=writer,
        reviewer=reviewer,
        config=config,
        renderer=renderer,
    )


_CONFIG_PATH: str = "config/agents.yaml"
_ORCHESTRATOR_FACTORY = create_orchestrator


def reload_config(signum=None, frame=None) -> None:
    global _CONFIG_PATH
    logger.info("Received signal %s, reloading config from %s", signum, _CONFIG_PATH)
    try:
        load_config(_CONFIG_PATH)
        logger.info("Config reloaded successfully.")
    except Exception:
        logger.exception("Failed to reload config")


def install_sighup_handler(config_path: str = "config/agents.yaml") -> None:
    global _CONFIG_PATH
    _CONFIG_PATH = config_path
    sighup = getattr(signal, "SIGHUP", None)
    if sighup is not None:
        signal.signal(sighup, reload_config)
        logger.info("SIGHUP handler installed for config reload.")
    else:
        logger.info("SIGHUP not available on this platform (Windows). Config reload disabled.")
