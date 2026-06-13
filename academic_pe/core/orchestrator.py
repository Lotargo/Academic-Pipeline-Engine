from __future__ import annotations

import logging
import os
import re
import signal
import threading
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Protocol

from academic_pe.core.config import AppConfig, TemplateMode, load_config, SectionPrompt
from academic_pe.agents.base import BaseAgent
from academic_pe.core.language import language_instruction, resolve_output_language
from academic_pe.core.prompting import DEFAULT_DRAFT_TEMPLATE, DEFAULT_PATCH_REVISION_TEMPLATE, DEFAULT_PLAN_TEMPLATE, DEFAULT_REVIEW_TEMPLATE, DEFAULT_REVISION_TEMPLATE, DEFAULT_VERIFY_TEMPLATE, render_template
from academic_pe.core.prompt_manifest_resolver import PromptManifestResolver
from academic_pe.core.section_patch import SectionPatchError, apply_line_replace_patch, add_line_numbers
from academic_pe.core.template_compat import template_section_to_section_prompt
from academic_pe.core.template_selector import TemplateSelector
from academic_pe.core.templates import RuntimePromptManifest, RuntimeTemplate
from academic_pe.core.translator import has_cyrillic, translate_markdown_to_ru

logger = logging.getLogger(__name__)


class PipelineCancelled(Exception):
    pass


class PipelineState(Enum):
    INIT = auto()
    PLANNING = auto()
    DRAFTING = auto()
    REVIEWING = auto()
    RENDERING = auto()
    DONE = auto()
    FAILED = auto()


_DEFAULT_TRANSITIONS: Dict[PipelineState, List[PipelineState]] = {
    PipelineState.INIT: [PipelineState.PLANNING, PipelineState.DRAFTING],
    PipelineState.PLANNING: [PipelineState.DRAFTING],
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
SectionDeltaFn = Callable[[str, str, str], None]


def strip_markdown_fences(text: str) -> str:
    if not text:
        return ""
    text_stripped = text.strip()
    
    # Match starting code fence: 3 or more backticks, followed by optional word characters and a newline
    start_match = re.match(r"^(`{3,})[a-zA-Z0-9_-]*\s*?\n", text_stripped)
    if start_match:
        fence = start_match.group(1)
        if text_stripped.endswith(fence):
            content = text_stripped[start_match.end():-len(fence)]
            return content.strip()
        else:
            rest = text_stripped[start_match.end():]
            if fence not in rest:
                return rest.strip()

    # 1. Check if the entire string is wrapped in a code fence
    pattern_strict = r"^```(?:markdown|latex|html|text|code)?\s*\n(.*?)\n```$"
    match_strict = re.match(pattern_strict, text_stripped, re.DOTALL | re.IGNORECASE)
    if match_strict:
        return match_strict.group(1).strip()
        
    # 2. Check if there is a code block inside containing the majority of the text
    pattern_search = r"```(?:markdown|latex|html|text|code)?\s*\n(.*?)\n```"
    matches = list(re.finditer(pattern_search, text_stripped, re.DOTALL | re.IGNORECASE))
    if len(matches) == 1:
        content = matches[0].group(1).strip()
        if len(content) > len(text_stripped) * 0.5:
            return content
            
    # 3. Simple fallback for starts/ends with triple backticks
    if text_stripped.startswith("```") and text_stripped.endswith("```"):
        lines = text_stripped.splitlines()
        if len(lines) >= 2:
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1] == "```":
                lines = lines[:-1]
            return "\n".join(lines).strip()
            
    return text


def parse_rejection_reasons(reason: str, sections: List[SectionPrompt]) -> Dict[str, str]:
    reasons_by_section: Dict[str, List[str]] = {s.name: [] for s in sections}
    general_reasons = []

    def normalize(s: str) -> str:
        return re.sub(r'[^a-zA-Z0-9]', '', s).lower()

    section_by_normalized_name = {normalize(s.name): s.name for s in sections}
    section_by_normalized_topic = {normalize(s.topic): s.name for s in sections}

    lines = reason.strip().splitlines()
    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue
        if line_str.startswith(('-', '*', '+')):
            line_str = line_str.lstrip('-*+').strip()

        matched_section_name = None
        bracket_match = re.match(r"^\[([^\]]+)\]\s*[:\-]?\s*(.*)$", line_str)
        if bracket_match:
            sec_candidate = bracket_match.group(1).strip()
            content = bracket_match.group(2).strip()
            norm_candidate = normalize(sec_candidate)
            if norm_candidate in section_by_normalized_name:
                matched_section_name = section_by_normalized_name[norm_candidate]
                line_str = content
            elif norm_candidate in section_by_normalized_topic:
                matched_section_name = section_by_normalized_topic[norm_candidate]
                line_str = content
            elif norm_candidate in ("general", "all"):
                general_reasons.append(content)
                continue
        else:
            # Check if line starts with "<section_candidate>:" or similar
            # e.g., "Theory: line 14: ..." or "State Machines: line 14: ..."
            for s in sections:
                name_prefix = s.name + ":"
                if line_str.lower().startswith(name_prefix.lower()):
                    matched_section_name = s.name
                    line_str = line_str[len(name_prefix):].strip()
                    break
                topic_prefix = s.topic + ":"
                if line_str.lower().startswith(topic_prefix.lower()):
                    matched_section_name = s.name
                    line_str = line_str[len(topic_prefix):].strip()
                    break

        if matched_section_name:
            reasons_by_section[matched_section_name].append(line_str)
        else:
            general_reasons.append(line_str)

    # Compile the final reason string for each section
    final_reasons: Dict[str, str] = {}
    for s in sections:
        section_specific = reasons_by_section[s.name]
        combined = []
        if general_reasons:
            combined.append("General issues:\n" + "\n".join(f"- {r}" for r in general_reasons))
        if section_specific:
            combined.append(f"Issues specific to section '{s.name}':\n" + "\n".join(f"- {r}" for r in section_specific))
        
        if combined:
            final_reasons[s.name] = "\n\n".join(combined)
        else:
            final_reasons[s.name] = "No specific issues identified for this section (verify coherence and document integration)."

    return final_reasons


class Orchestrator:
    def __init__(
        self,
        writer: BaseAgent,
        config: AppConfig,
        reviewer: Optional[BaseAgent] = None,
        renderer: Optional[Renderer] = None,
        runtime_template: Optional[RuntimeTemplate] = None,
        runtime_prompt_manifest: Optional[RuntimePromptManifest] = None,
        continuation_source: Optional[Dict[str, Any]] = None,
    ):
        self._writer = writer
        self._reviewer = reviewer
        self._renderer = renderer
        self._config = config
        self.runtime_template = runtime_template
        self.runtime_prompt_manifest = runtime_prompt_manifest
        self.continuation_source = continuation_source
        self._state: PipelineState = PipelineState.INIT
        self.context: Dict[str, str] = {}
        self.user_topic: str = ""
        self.user_instructions: str = ""
        self._draft_plan: str = ""
        self._state_history: List[PipelineState] = []
        self._hooks: Dict[str, List[HookFn]] = {
            "on_enter": [],
            "on_exit": [],
        }
        self._section_delta_hooks: List[SectionDeltaFn] = []
        self._transitions: Dict[PipelineState, List[PipelineState]] = dict(_DEFAULT_TRANSITIONS)
        self._cancel_event: threading.Event = threading.Event()
        self.first_attempt_reason: Optional[str] = None

    def _continuation_context(self) -> str:
        source = self.continuation_source
        if not source:
            return ""

        parts: List[str] = []
        source_type = source.get("source_type") or "generated"
        parts.append(f"Source type: {source_type}")

        source_topic = source.get("topic")
        if source_topic:
            parts.append(f"Previous document topic/title: {source_topic}")

        source_instructions = source.get("instructions")
        if source_instructions:
            parts.append(f"Previous document instructions: {source_instructions}")

        document_plan = source.get("document_plan")
        if document_plan:
            parts.append("[Previous Document Plan]\n" + str(document_plan))

        context = source.get("context")
        if isinstance(context, dict):
            section_parts = []
            for name, content in context.items():
                if name == "document_plan" or not content:
                    continue
                section_parts.append(f"## {name}\n{content}")
            if section_parts:
                parts.append("[Previous Document Sections]\n" + "\n\n".join(section_parts))

        return "\n\n".join(parts)

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

    def on_section_delta(self, callback: SectionDeltaFn) -> None:
        self._section_delta_hooks.append(callback)

    def cancel(self) -> None:
        self._cancel_event.set()

    def _check_cancelled(self) -> None:
        if self._cancel_event.is_set():
            raise PipelineCancelled("Pipeline was cancelled by user")

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

    def _emit_section_delta(self, section_name: str, delta: str, accumulated: str) -> None:
        for hook in self._section_delta_hooks:
            hook(section_name, delta, accumulated)

    def _set_section_content(self, section_name: str, content: str) -> None:
        cleaned_content = strip_markdown_fences(content)
        self.context[section_name] = cleaned_content
        self._emit_section_delta(section_name, cleaned_content, cleaned_content)

    def _document_memory(self, current_section_name: str = "", with_line_numbers: bool = False) -> str:
        parts: List[str] = []
        continuation_context = self._continuation_context()
        if continuation_context:
            parts.append("[Continuation Source]\n" + continuation_context)

        if self._draft_plan:
            parts.append("[Document Plan]\n" + self._draft_plan)

        previous_sections = []
        subsequent_sections = []
        is_subsequent = False

        for section in self._config.pipeline.sections:
            if section.name == current_section_name:
                is_subsequent = True
                continue
            content = self.context.get(section.name)
            if content:
                if is_subsequent:
                    subsequent_sections.append(f"## {section.topic}\n{content}")
                else:
                    previous_sections.append(f"## {section.topic}\n{content}")

        if previous_sections:
            parts.append("[Already Written Sections (Before This Section)]\n" + "\n\n".join(previous_sections))

        if subsequent_sections:
            parts.append("[Already Written Sections (After This Section)]\n" + "\n\n".join(subsequent_sections))

        if current_section_name and self.context.get(current_section_name):
            content = self.context[current_section_name]
            if with_line_numbers:
                content = add_line_numbers(content)
            parts.append("[Current Section Before Revision]\n" + content)

        return "\n\n".join(parts)

    def revert(self) -> PipelineState:
        if not self._state_history:
            raise PipelineError("No previous state to revert to.")
        prev = self._state_history.pop()
        logger.info("Revert: %s -> %s", self._state.name, prev.name)
        self._state = prev
        return prev

    def run_pipeline(self, render_artifact: bool = True) -> str:
        logger.info("Pipeline started.")
        output_path = "(no output)"
        raw_language_policy = getattr(self._config.pipeline, "language", "auto")
        language_policy = getattr(raw_language_policy, "value", raw_language_policy)
        prompt_text = " ".join(x for x in [self.user_topic, self.user_instructions] if x)
        target_language = resolve_output_language(prompt_text, str(language_policy))

        try:
            # --- PLANNING ---
            self.transition_to(PipelineState.PLANNING)
            plan_task = render_template(
                DEFAULT_PLAN_TEMPLATE,
                {
                    "sections": self._config.pipeline.sections,
                    "language": target_language,
                    "language_instruction": language_instruction(target_language),
                    "user_topic": self.user_topic,
                    "user_instructions": self.user_instructions,
                    "continuation_context": self._continuation_context(),
                    "academic_mode": getattr(self._config.pipeline, "academic_mode", False),
                    "output_dir": self._config.pipeline.output_dir,
                },
            )
            logger.info("Creating document plan before drafting sections.")
            self._draft_plan = self._writer.process(plan_task)
            self._set_section_content("document_plan", self._draft_plan)

            # --- DRAFTING ---
            self.transition_to(PipelineState.DRAFTING)

            for section in self._config.pipeline.sections:
                self._check_cancelled()
                task = render_template(
                    DEFAULT_DRAFT_TEMPLATE,
                    {
                        "section": section,
                        "language": target_language,
                        "language_instruction": language_instruction(target_language),
                        "user_topic": self.user_topic,
                        "user_instructions": self.user_instructions,
                        "continuation_context": self._continuation_context(),
                        "academic_mode": getattr(self._config.pipeline, "academic_mode", False),
                        "output_dir": self._config.pipeline.output_dir,
                    },
                )
                logger.debug("Drafting section: %s", section.name)

                max_sandbox_retries = 3
                draft_content = ""
                error_feedback = ""

                for attempt in range(max_sandbox_retries):
                    self._check_cancelled()
                    current_task = task
                    if error_feedback:
                        current_task += f"\n\n[Sandbox Error Feedback]\nYour previous code failed. {error_feedback}"

                    draft_parts: List[str] = []

                    def on_delta(delta: str, section_name: str = section.name) -> None:
                        draft_parts.append(delta)
                        self._emit_section_delta(section_name, delta, "".join(draft_parts))

                    draft_content = self._writer.process(
                        current_task,
                        context=self._document_memory(section.name),
                        on_delta=on_delta,
                        document_sections=self.context,
                    )

                    academic_mode = getattr(self._config.pipeline, "academic_mode", False)
                    if academic_mode:
                        try:
                            from academic_pe.core.sandbox import execute_sandbox_blocks
                            draft_content = execute_sandbox_blocks(draft_content)
                            break
                        except Exception as exc:
                            from academic_pe.core.sandbox import SandboxExecutionError
                            if isinstance(exc, SandboxExecutionError):
                                logger.warning(
                                    "Sandbox execution failed for section %s (attempt %d/%d): %s",
                                    section.name,
                                    attempt + 1,
                                    max_sandbox_retries,
                                    exc,
                                )
                                if attempt == max_sandbox_retries - 1:
                                    raise PipelineError(f"Failed to generate valid executable code in section {section.name} after {max_sandbox_retries} attempts. Error: {exc}") from exc
                                error_feedback = f"The code block you wrote:\n```python-run\n{exc.code}\n```\nfailed with error:\n{exc}"
                            else:
                                raise
                    else:
                        break

                draft_content = strip_markdown_fences(draft_content)
                if target_language == "ru" and not has_cyrillic(draft_content):
                    logger.info("Translating section %s to Russian...", section.name)
                    draft_content = translate_markdown_to_ru(draft_content)
                self.context[section.name] = strip_markdown_fences(draft_content)

            # --- REVIEWING ---
            self.transition_to(PipelineState.REVIEWING)

            from academic_pe.agents.writer import ReviewerAgent

            max_retries = 3
            review_focus = ""
            for attempt in range(max_retries):
                self._check_cancelled()
                if self._reviewer is None:
                    logger.info("No reviewer configured, skipping review.")
                    break

                full_text_parts = []
                for s in self._config.pipeline.sections:
                    sec_content = self.context.get(s.name, "")
                    numbered_content = add_line_numbers(sec_content)
                    full_text_parts.append(
                        f"=== Section: {s.name} ===\n{numbered_content}"
                    )
                full_text = "\n\n".join(full_text_parts)
                # --- Programmatic Quality Gate Validation ---
                from academic_pe.core.quality_gate import run_all as run_quality_gate
                qg_result = run_quality_gate(self.context, self._config.quality_gate)
                if not qg_result.passed:
                    # Quality gate failed, bypass LLM reviewer and auto-generate rejection
                    logger.warning("Quality Gate failed during review loop: %s", qg_result.issues)
                    critique = "REJECTED\n" + "\n".join(f"- [general]: Quality Gate issue: {issue}" for issue in qg_result.issues)
                else:
                    critique = self._reviewer.process(
                        render_template(
                            DEFAULT_REVIEW_TEMPLATE,
                            {
                                "language": target_language,
                                "review_focus": review_focus,
                                "sections": self._config.pipeline.sections,
                                "continuation_context": self._continuation_context(),
                                "academic_mode": getattr(self._config.pipeline, "academic_mode", False),
                                "output_dir": self._config.pipeline.output_dir,
                            },
                        ),
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
                logger.warning("Reviewer rejected (attempt %d/%d): %s", attempt + 1, max_retries, reason)
                if self.first_attempt_reason is None:
                    self.first_attempt_reason = reason
                review_focus = reason

                if attempt < max_retries - 1:
                    logger.info("Returning to DRAFTING for revision...")
                    self.transition_to(PipelineState.DRAFTING)
                    
                    reasons_by_section = parse_rejection_reasons(
                        reason, self._config.pipeline.sections
                    )

                    for section in self._config.pipeline.sections:
                        self._check_cancelled()
                        sec_reason = reasons_by_section.get(section.name, reason)
                        task = render_template(
                            DEFAULT_PATCH_REVISION_TEMPLATE,
                            {
                                "section": section,
                                "reviewer_reason": sec_reason,
                                "language": target_language,
                                "language_instruction": language_instruction(target_language),
                                "user_topic": self.user_topic,
                                "user_instructions": self.user_instructions,
                                "continuation_context": self._continuation_context(),
                                "academic_mode": getattr(self._config.pipeline, "academic_mode", False),
                                "output_dir": self._config.pipeline.output_dir,
                            },
                        )
                        current_content = self.context.get(section.name, "")
                        patch_text = self._writer.process(
                            task,
                            context=self._document_memory(section.name, with_line_numbers=True),
                            document_sections=self.context,
                        )
                        try:
                            revised_content = apply_line_replace_patch(current_content, patch_text)
                            revised_content = strip_markdown_fences(revised_content)
                            academic_mode = getattr(self._config.pipeline, "academic_mode", False)
                            if academic_mode:
                                from academic_pe.core.sandbox import execute_sandbox_blocks
                                revised_content = execute_sandbox_blocks(revised_content)
                        except Exception as exc:
                            logger.warning(
                                "Patch revision failed for section %s: %s. Falling back to full-section revision.",
                                section.name,
                                exc,
                            )
                            max_sandbox_retries = 3
                            error_feedback = ""
                            fallback_task = render_template(
                                DEFAULT_REVISION_TEMPLATE,
                                {
                                    "section": section,
                                    "reviewer_reason": sec_reason,
                                    "language": target_language,
                                    "language_instruction": language_instruction(target_language),
                                    "user_topic": self.user_topic,
                                    "user_instructions": self.user_instructions,
                                    "continuation_context": self._continuation_context(),
                                    "academic_mode": getattr(self._config.pipeline, "academic_mode", False),
                                    "output_dir": self._config.pipeline.output_dir,
                                },
                            )
                            for fallback_attempt in range(max_sandbox_retries):
                                self._check_cancelled()
                                current_fallback_task = fallback_task
                                if error_feedback:
                                    current_fallback_task += f"\n\n[Sandbox Error Feedback]\nYour previous code failed. {error_feedback}"

                                revised_content = self._writer.process(
                                    current_fallback_task,
                                    context=self._document_memory(section.name),
                                    document_sections=self.context,
                                )
                                revised_content = strip_markdown_fences(revised_content)

                                academic_mode = getattr(self._config.pipeline, "academic_mode", False)
                                if academic_mode:
                                    try:
                                        from academic_pe.core.sandbox import execute_sandbox_blocks
                                        revised_content = execute_sandbox_blocks(revised_content)
                                        break
                                    except Exception as e_exc:
                                        from academic_pe.core.sandbox import SandboxExecutionError
                                        if isinstance(e_exc, SandboxExecutionError):
                                            logger.warning(
                                                "Fallback sandbox execution failed for section %s (attempt %d/%d): %s",
                                                section.name,
                                                fallback_attempt + 1,
                                                max_sandbox_retries,
                                                e_exc,
                                            )
                                            if fallback_attempt == max_sandbox_retries - 1:
                                                raise PipelineError(f"Failed to generate valid executable code in section {section.name} fallback after {max_sandbox_retries} attempts. Error: {e_exc}") from e_exc
                                            error_feedback = f"The code block you wrote:\n```python-run\n{e_exc.code}\n```\nfailed with error:\n{e_exc}"
                                        else:
                                            raise
                                else:
                                    break

                        if target_language == "ru" and not has_cyrillic(revised_content):
                            logger.info("Translating revised section %s to Russian...", section.name)
                            revised_content = translate_markdown_to_ru(revised_content)
                        self._set_section_content(section.name, revised_content)

                    # --- Self-Verification Step ---
                    if self.first_attempt_reason:
                        logger.info("Starting writer self-verification against first reviewer feedback...")
                        verify_reasons_by_section = parse_rejection_reasons(
                            self.first_attempt_reason, self._config.pipeline.sections
                        )
                        for section in self._config.pipeline.sections:
                            self._check_cancelled()
                            sec_verify_reason = verify_reasons_by_section.get(section.name, self.first_attempt_reason)
                            verified = False
                            for verify_attempt in range(2):
                                verify_task = render_template(
                                    DEFAULT_VERIFY_TEMPLATE,
                                    {
                                        "section": section,
                                        "first_attempt_reason": sec_verify_reason,
                                        "language": target_language,
                                        "language_instruction": language_instruction(target_language),
                                        "user_topic": self.user_topic,
                                        "user_instructions": self.user_instructions,
                                        "continuation_context": self._continuation_context(),
                                        "academic_mode": getattr(self._config.pipeline, "academic_mode", False),
                                        "output_dir": self._config.pipeline.output_dir,
                                    }
                                )
                                response = self._writer.process(
                                    verify_task,
                                    context=self._document_memory(section.name),
                                    document_sections=self.context,
                                )
                                if response.strip() == "VERIFIED":
                                    logger.info("Section %s verified successfully.", section.name)
                                    verified = True
                                    break
                                else:
                                    logger.warning(
                                        "Section %s verification failed. Writer corrected the text (attempt %d/2).",
                                        section.name, verify_attempt + 1
                                    )
                                    academic_mode = getattr(self._config.pipeline, "academic_mode", False)
                                    if academic_mode:
                                        try:
                                            from academic_pe.core.sandbox import execute_sandbox_blocks
                                            response = execute_sandbox_blocks(response)
                                        except Exception as exc:
                                            logger.warning("Sandbox run failed during self-verification for %s: %s", section.name, exc)
                                    if target_language == "ru" and not has_cyrillic(response):
                                        logger.info("Translating verified section %s to Russian...", section.name)
                                        response = translate_markdown_to_ru(response)
                                    self._set_section_content(section.name, response)

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

            if render_artifact and self._renderer is not None:
                from academic_pe.tools.export_qa import resolve_export_filename

                title = self._config.pipeline.title or self.user_topic
                if title == "GENERATED ACADEMIC PAPER" and self.user_topic:
                    title = self.user_topic
                output_filename = resolve_export_filename(title, self._config.pipeline.output_filename)
                output_dir = self._config.pipeline.output_dir
                os.makedirs(output_dir, exist_ok=True)
                output_path = os.path.join(output_dir, output_filename)

                import inspect
                sig = inspect.signature(self._renderer)
                if "config" in sig.parameters:
                    output_path = self._renderer(self.context, output_filename=output_path, config=self._config)
                else:
                    output_path = self._renderer(self.context, output_filename=output_path)
            elif render_artifact:
                output_path = "(no renderer configured)"
                logger.warning("No renderer configured, skipping DOCX generation.")
            else:
                output_path = ""
                logger.info("Artifact rendering skipped. Draft content is ready for explicit export.")

            # --- DONE ---
            self.transition_to(PipelineState.DONE)
            logger.info("Pipeline finished. Artifact: %s", output_path)

        except PipelineCancelled:
            self._state = PipelineState.FAILED
            raise
        except PipelineError:
            raise
        except Exception:
            logger.exception("Pipeline failed at state %s", self._state.name)
            self._state = PipelineState.FAILED
            raise PipelineError(
                f"Pipeline failed at {self._state.name}. Check logs for details."
            ) from None

        return output_path


def _apply_runtime_template(
    config: AppConfig,
    runtime_template: RuntimeTemplate,
) -> AppConfig:
    resolved_config = config.model_copy(deep=True)
    resolved_config.pipeline.sections = [
        template_section_to_section_prompt(section)
        for section in runtime_template.sections
    ]
    return resolved_config


def should_preserve_topic(instructions: str) -> bool:
    if not instructions:
        return False
    instr_lower = instructions.lower()
    preserve_phrases = [
        "не переименовывать тему",
        "не переименовывай тему",
        "не менять тему",
        "тему не менять",
        "тему не переименовывать",
        "keep the topic as is",
        "do not rename the topic",
        "do not rename",
        "do not change the topic",
        "do not change topic",
        "keep topic",
    ]
    return any(phrase in instr_lower for phrase in preserve_phrases)


def rewrite_document_topic(
    topic: str,
    instructions: str,
    writer_agent: BaseAgent,
) -> str:
    if not topic:
        return ""

    if should_preserve_topic(instructions):
        return topic

    prompt = f"""You are an expert academic editor.
Your task is to refine the document topic into a highly professional, academic, and stylized title.

User Topic: "{topic}"
User Instructions/Constraints: "{instructions or '(none)'}"

Rules:
1. If the User Instructions explicitly state that the topic/title must not be changed, must remain exactly as is, or must not be renamed (e.g. "не переименовывать тему", "do not rename", etc.), you MUST return the User Topic exactly as is.
2. Otherwise, write a more correct, suitable, and stylistically refined academic title for the paper based on the topic.
3. The title must be in the same language as the User Topic.
4. Return ONLY the final title. Do not include any explanations, quotes, or introductory text.
"""
    refined = writer_agent.process(prompt)
    return refined.strip().strip('"\'')


def create_orchestrator_from_config(
    config: AppConfig,
    renderer: Optional[Renderer] = None,
    template_selector: Optional[TemplateSelector] = None,
    prompt_manifest_resolver: Optional[PromptManifestResolver] = None,
    user_topic: str = "",
    user_instructions: str = "",
    continuation_source: Optional[Dict[str, Any]] = None,
) -> Orchestrator:
    from academic_pe.agents.factory import create_agent

    writer_cfg = config.agents.get("writer")
    if not writer_cfg:
        raise ValueError("Writer agent configuration is missing")

    # Refine topic using writer agent if provider is not mock
    refined_topic = user_topic
    if user_topic and getattr(writer_cfg.provider, "value", writer_cfg.provider) != "mock":
        if should_preserve_topic(user_instructions):
            logger.info("Preserving original topic due to user instructions constraint: '%s'", user_topic)
        else:
            temp_writer = create_agent("writer", writer_cfg, retry_cfg=config.retry)
            refined_topic = rewrite_document_topic(user_topic, user_instructions, temp_writer)
            logger.info("Refined topic: '%s' -> '%s'", user_topic, refined_topic)

            # Update section topics to use refined topic
            for sec in config.pipeline.sections:
                if sec.topic.startswith(user_topic + ":"):
                    sec.topic = sec.topic.replace(user_topic + ":", refined_topic + ":", 1)
                elif sec.topic == user_topic:
                    sec.topic = refined_topic

    selector = template_selector or _create_template_selector(config)
    runtime_template, runtime_prompt_manifest = selector.select(
        config,
        topic=refined_topic,
        instructions=user_instructions,
    )
    resolved_config = _apply_runtime_template(config, runtime_template)
    
    # Set resolved config pipeline title to refined topic
    resolved_config.pipeline.title = refined_topic

    resolver = prompt_manifest_resolver or PromptManifestResolver()
    resolved_config = resolver.resolve_app_config(resolved_config, runtime_prompt_manifest)

    writer = create_agent("writer", resolved_config.agents["writer"], retry_cfg=resolved_config.retry)
    reviewer = None
    if "reviewer" in resolved_config.agents:
        reviewer = create_agent("reviewer", resolved_config.agents["reviewer"], retry_cfg=resolved_config.retry)

    orchestrator = Orchestrator(
        writer=writer,
        reviewer=reviewer,
        config=resolved_config,
        renderer=renderer,
        runtime_template=runtime_template,
        runtime_prompt_manifest=runtime_prompt_manifest,
        continuation_source=continuation_source,
    )
    orchestrator.user_topic = refined_topic
    orchestrator.user_instructions = user_instructions
    return orchestrator


def _create_template_selector(config: AppConfig) -> TemplateSelector:
    raw_mode = getattr(config.pipeline.template_mode, "value", config.pipeline.template_mode)
    if TemplateMode(str(raw_mode)) != TemplateMode.auto:
        return TemplateSelector()

    planner_cfg = config.agents.get("planner")
    if planner_cfg is None:
        return TemplateSelector()

    from academic_pe.agents.factory import _build_llm
    from academic_pe.core.planner_agent import PlannerAgent

    planner = PlannerAgent(
        planner_cfg,
        _build_llm(planner_cfg, retry_cfg=config.retry, cb_cfg=config.circuit_breaker),
    )
    return TemplateSelector(planner=planner)


def create_orchestrator(
    config_path: str = "config/agents.yaml",
    renderer: Optional[Renderer] = None,
) -> Orchestrator:
    config = load_config(config_path)
    return create_orchestrator_from_config(config, renderer=renderer)


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
