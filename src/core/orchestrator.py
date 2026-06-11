from __future__ import annotations

import logging
from enum import Enum, auto
from typing import Dict, List, Optional, Protocol

from src.core.config import AppConfig, load_config
from src.core.llm import create_provider
from src.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class PipelineState(Enum):
    INIT = auto()
    DRAFTING = auto()
    REVIEWING = auto()
    RENDERING = auto()
    DONE = auto()
    FAILED = auto()


_TRANSITIONS: Dict[PipelineState, List[PipelineState]] = {
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
    def __call__(self, content: Dict[str, str], output_filename: str) -> str:
        ...


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

    @property
    def state(self) -> PipelineState:
        return self._state

    def transition_to(self, new_state: PipelineState) -> None:
        allowed = _TRANSITIONS.get(self._state, [])
        if new_state not in allowed:
            raise InvalidTransitionError(
                f"Cannot transition from {self._state.name} to {new_state.name}. "
                f"Allowed: {[s.name for s in allowed]}"
            )
        logger.info("State: %s -> %s", self._state.name, new_state.name)
        self._state = new_state

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

                if critique.strip().upper().startswith("APPROVED"):
                    logger.info("Reviewer approved the content.")
                    break

                logger.warning("Reviewer rejected (attempt %d/%d): %s", attempt + 1, max_retries, critique[:100])

                if attempt < max_retries - 1:
                    logger.info("Returning to DRAFTING for revision...")
                    self.transition_to(PipelineState.DRAFTING)
                    for section in self._config.pipeline.sections:
                        task = (
                            f"Revise the chapter about {section.topic}. "
                            f"Address these issues: {critique[:500]}. "
                            f"{section.instruction}"
                        )
                        self.context[section.name] = self._writer.process(task)
                    self.transition_to(PipelineState.REVIEWING)
                else:
                    logger.error("Max retries reached. Proceeding to rendering with current content.")

            # --- QUALITY GATE ---
            from src.core.quality_gate import run_all as run_quality_gate
            qg_result = run_quality_gate(self.context, self._config.quality_gate)
            if not qg_result.passed:
                for issue in qg_result.issues:
                    logger.warning("Quality Gate: %s", issue)
            else:
                logger.info("Quality Gate: all checks passed.")

            # --- RENDERING ---
            self.transition_to(PipelineState.RENDERING)

            if self._renderer is not None:
                output_path = self._renderer(self.context, output_filename="Final_Academic_Paper.docx")
            else:
                output_path = "(no renderer configured)"
                logger.warning("No renderer configured, skipping DOCX generation.")

            # --- DONE ---
            self.transition_to(PipelineState.DONE)
            logger.info("Pipeline finished. Artifact: %s", output_path)

        except Exception:
            logger.exception("Pipeline failed at state %s", self._state.name)
            self._state = PipelineState.FAILED
            raise PipelineError(
                f"Pipeline failed at {self._state.name}. Check logs for details."
            ) from None

        return output_path


def _build_agent(cfg: AppConfig, retry_cfg: Optional[AppConfig] = None) -> BaseAgent:
    from src.core.config import AgentConfig as AC
    from src.core.config import RetryConfig as RetryCfg
    from src.core.llm import RetryConfig as LLMRetryConfig

    if not isinstance(cfg, AC):
        raise ValueError("Invalid agent configuration")

    rc = None
    if retry_cfg is not None and isinstance(retry_cfg, RetryCfg) and retry_cfg.max_retries > 0:
        rc = LLMRetryConfig(
            max_retries=retry_cfg.max_retries,
            base_delay=retry_cfg.base_delay,
            max_delay=retry_cfg.max_delay,
        )

    llm = create_provider(provider=cfg.provider, base_url=cfg.base_url, retry_config=rc)
    return BaseAgent(cfg, llm)


def create_orchestrator(
    config_path: str = "config/agents.yaml",
    renderer: Optional[Renderer] = None,
) -> Orchestrator:
    config = load_config(config_path)

    writer_cfg = config.agents.get("writer")
    if not writer_cfg:
        raise ValueError("Writer agent configuration is missing")

    writer = _build_agent(writer_cfg, config.retry)
    reviewer = _build_agent(config.agents["reviewer"], config.retry) if "reviewer" in config.agents else None

    return Orchestrator(
        writer=writer,
        reviewer=reviewer,
        config=config,
        renderer=renderer,
    )
