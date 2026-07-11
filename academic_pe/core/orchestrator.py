from __future__ import annotations

import logging
from datetime import datetime
import json
import os
import hashlib
import re
import signal
import threading
import unicodedata
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Protocol

from academic_pe.core.config import AppConfig, TemplateMode, load_config, SectionPrompt
from academic_pe.core.continuation import detect_terminal_sections, infer_continuation_intent
from academic_pe.core.document_structure import HeadingPolicy, SemanticRole, is_renderable_section, renderable_sections
from academic_pe.core.document_state import extract_document_state
from academic_pe.core.calculation_audit import CalculationEntry, CalculationLedger
from academic_pe.core.document_ledger import DocumentLedger
from academic_pe.agents.base import BaseAgent
from academic_pe.core.language import language_instruction, resolve_output_language
from academic_pe.core.prompting import DEFAULT_DRAFT_TEMPLATE, DEFAULT_MERGE_OPERATION_TEMPLATE, DEFAULT_PATCH_REVISION_TEMPLATE, DEFAULT_PLAN_TEMPLATE, DEFAULT_REVIEW_TEMPLATE, DEFAULT_REVISION_TEMPLATE, DEFAULT_VERIFY_TEMPLATE, render_template
from academic_pe.core.prompt_manifest_resolver import PromptManifestResolver
from academic_pe.core.section_patch import SectionPatchError, apply_line_replace_patch, add_line_numbers
from academic_pe.core.template_compat import template_section_to_section_prompt
from academic_pe.core.template_selector import TemplateSelector
from academic_pe.core.templates import RuntimePromptManifest, RuntimeTemplate, TemplateSection
from academic_pe.core.translator import has_cyrillic, translate_markdown_to_ru
from academic_pe.core.merge_operations import (
    EditPlan,
    apply_merge_operations,
    build_default_edit_plan,
    compact_merge_patch_metadata,
    parse_merge_operation_payload,
    required_content_roles,
    validate_merge_operation_targets,
)
from academic_pe.manifests.resolver import ArtifactManifestResolver
from academic_pe.core.registry import (
    RegistryStore, NoopRegistryStore, Run, RunAgent, RuntimeSnapshot, Section, Source, Artifact, Evaluation
)

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


_COMMON_MOJIBAKE_REPLACEMENTS = {
    "\u2014": " - ",
    "\u2013": "-",
    "\u2011": "-",
    "\u201c": '"',
    "\u201d": '"',
    "\u2018": "'",
    "\u2019": "'",
    "\u2026": "...",
    "\u2022": "-",
    "\u2192": "->",
    "\u00a0": " ",
    "\u202f": " ",
    "\u2009": " ",
    "вЂ”": " - ",
    "вЂ“": "-",
    "вЂ‘": "-",
    "вЂњ": '"',
    "вЂќ": '"',
    "вЂ˜": "'",
    "вЂ™": "'",
    "вЂ¦": "...",
    "вЂў": "-",
    "в†’": "->",
    "тАФ": " - ",
    "тАУ": "-",
    "тАС": "-",
    "тАЬ": '"',
    "тАЭ": '"',
    "тАШ": "'",
    "тАЩ": "'",
    "тАж": "...",
    "тАв": "-",
    "тЖТ": "->",
}


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


def normalize_generated_text(text: str) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize("NFC", text).replace("\ufeff", "")
    for bad, replacement in sorted(_COMMON_MOJIBAKE_REPLACEMENTS.items(), key=lambda item: len(item[0]), reverse=True):
        normalized = normalized.replace(bad, replacement)
    normalized = re.sub(r"[ \t]{2,}", " ", normalized)
    normalized = re.sub(r" ?-  ?", " - ", normalized)
    normalized = re.sub(r"\s+([,.;:!?])", r"\1", normalized)
    return normalized


def compact_log_preview(text: str, max_chars: int = 700) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


def _quality_gate_review_issue(issue: str) -> str:
    section_match = re.search(r"Section '([^']+)'", issue)
    line_match = re.search(r"\bline (\d+)\b", issue)
    section = section_match.group(1) if section_match else "general"
    if line_match:
        return f"- [{section}]: line {line_match.group(1)}: Quality Gate issue: {issue}"
    return f"- [{section}]: Quality Gate issue: {issue}"


_SECTION_HEADING_RE = re.compile(
    r"^(?P<prefix>#{1,6}\s+|===\s*Section:\s*)(?P<label>.+?)(?:\s*===)?\s*$",
    re.IGNORECASE | re.MULTILINE,
)

_SECTION_NAME_ALIASES: Dict[str, List[str]] = {
    "introduction": ["intro", "введение"],
    "main_part": ["main part", "body", "основная часть"],
    "conclusion": ["summary", "заключение", "вывод", "выводы"],
    "references": ["bibliography", "список литературы", "источники"],
}


def _normalize_section_label(label: str) -> str:
    label = re.sub(r"^\s*\d+(?:[.)]\d+)*[.)]?\s*", "", label.strip())
    label = re.sub(r"[*_`#]+", "", label)
    return re.sub(r"[\W_]+", "", label, flags=re.UNICODE).lower()


def _section_label_set(section: SectionPrompt) -> set[str]:
    labels = {
        _normalize_section_label(section.name),
        _normalize_section_label(section.topic),
    }
    for alias in _SECTION_NAME_ALIASES.get(section.name, []):
        labels.add(_normalize_section_label(alias))
    return {label for label in labels if label}


def _match_configured_section(label: str, sections: List[SectionPrompt]) -> Optional[str]:
    normalized = _normalize_section_label(label)
    if not normalized:
        return None
    for section in sections:
        if normalized in _section_label_set(section):
            return section.name
    return None


def isolate_current_section_revision(
    text: str,
    current_section: SectionPrompt,
    sections: List[SectionPrompt],
) -> str:
    stripped = strip_markdown_fences(text).strip()
    matches = []
    for match in _SECTION_HEADING_RE.finditer(stripped):
        section_name = _match_configured_section(match.group("label"), sections)
        if section_name:
            matches.append((match.start(), match.end(), section_name))

    if not matches:
        return stripped

    other_matches = [match for match in matches if match[2] != current_section.name]
    if not other_matches:
        return stripped

    current_matches = [match for match in matches if match[2] == current_section.name]
    if current_matches:
        start = current_matches[0][0]
        following = [match for match in matches if match[0] > start]
        end = following[0][0] if following else len(stripped)
        extracted = stripped[start:end].strip()
        if extracted:
            logger.warning(
                "Full-section revision for %s included other configured sections; extracted current section block.",
                current_section.name,
            )
            return extracted

    section_order = {section.name: idx for idx, section in enumerate(sections)}
    current_idx = section_order.get(current_section.name, -1)
    if current_idx >= 0 and all(section_order.get(match[2], -1) > current_idx for match in other_matches):
        earliest_other = min(other_matches, key=lambda match: match[0])
        extracted = stripped[: earliest_other[0]].strip()
        if extracted:
            logger.warning(
                "Full-section revision for %s appended later sections; trimmed output before the next section heading.",
                current_section.name,
            )
            return extracted

    section_names = sorted({match[2] for match in matches})
    raise SectionPatchError(
        "Full-section revision returned multiple configured sections: "
        + ", ".join(section_names)
        + ". Return only the current section."
    )


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
        reference_materials: Optional[List[Dict[str, Any]]] = None,
        web_search_enabled: bool = False,
        planner: Optional[BaseAgent] = None,
        researcher: Optional[BaseAgent] = None,
        registry_store: Optional[RegistryStore] = None,
        run_id: Optional[str] = None,
    ):
        self._writer = writer
        self._reviewer = reviewer
        self._has_dedicated_planner = planner is not None
        self._planner = planner or writer
        self._researcher = researcher
        self._renderer = renderer
        self._config = config
        self.runtime_template = runtime_template
        self.runtime_prompt_manifest = runtime_prompt_manifest
        self.reference_materials = reference_materials or []
        self.web_search_enabled = web_search_enabled
        self.continuation_source = continuation_source
        self.search_findings = ""
        self._document_ledger = (
            extract_document_state(continuation_source).ledger
            if continuation_source
            else DocumentLedger()
        )
        self._calculation_ledger = (
            extract_document_state(continuation_source).calculation_ledger
            if continuation_source
            else CalculationLedger()
        )
        for item in self.reference_materials:
            if not isinstance(item, dict):
                continue
            filename = str(item.get("filename") or item.get("title") or "").strip()
            if filename:
                self._document_ledger.register_source(
                    title=filename,
                    url=item.get("url"),
                    source_type="reference_material",
                    reliability="user_provided",
                )
        self._registry_store = registry_store or NoopRegistryStore()

        # Resolve run_id
        if not run_id:
            output_dir = getattr(config.pipeline, "output_dir", "")
            basename = os.path.basename(output_dir)
            if re.match(r"^run_\d{8}_\d{6}$", basename):
                run_id = basename
            else:
                from datetime import datetime
                run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.run_id = run_id


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
        self.self_critique_summaries: List[Dict[str, str]] = []

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

        previous_prompt = source.get("previous_prompt")
        if previous_prompt:
            parts.append("[Previous User Prompt]\n" + str(previous_prompt))

        runtime_template = source.get("runtime_template")
        if isinstance(runtime_template, dict):
            parts.append("[Previous Runtime Template]\n" + str(runtime_template))

        runtime_prompt_manifest = source.get("runtime_prompt_manifest")
        if isinstance(runtime_prompt_manifest, dict):
            parts.append("[Previous Runtime Prompt Manifest]\n" + str(runtime_prompt_manifest))

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

    def _generate_search_queries(self) -> List[str]:
        from academic_pe.core.llm import _call_provider_generate
        system_prompt = (
            "You are a professional research strategist for a document-planning pipeline. "
            "Based on the user topic and instructions, generate exactly 3 distinct web search queries. "
            "Each query must have a different intent: (1) authoritative/primary sources or official documentation, "
            "(2) recent evidence, data, standards, or reputable reporting, and (3) critical context, limitations, or competing viewpoints. "
            "Use precise domain terms, named entities, dates, locations, standards, or methods from the user request. "
            "Avoid vague beginner queries such as 'what is ...' unless the user explicitly needs definitions. "
            "Do not fabricate source names. Do not use site filters unless a likely authoritative domain is implied by the request. "
            "Return a simple numbered list, one query per line (e.g. '1. query one'). No markdown, no quotes, no commentary."
        )
        user_prompt = f"Topic: {self.user_topic}\nInstructions: {self.user_instructions}"
        try:
            raw_queries = _call_provider_generate(
                self._planner.llm,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=self._planner.config.model,
                temperature=0.3,
                reasoning_effort=getattr(self._planner.config.reasoning_effort, "value", self._planner.config.reasoning_effort),
            )
            queries = []
            for line in raw_queries.splitlines():
                line = line.strip()
                if not line:
                    continue
                match = re.match(r"^(?:\d+[\).]|[-*])\s*(.+)$", line)
                if match:
                    queries.append(match.group(1).strip())
                elif len(line) > 5:
                    queries.append(line)
            return queries[:3]
        except Exception as e:
            logger.error("Failed to generate search queries: %s", e)
            return []

    def _resolved_contract_data(self) -> Optional[dict]:
        manifest = self.runtime_prompt_manifest
        if manifest is None:
            return None

        metadata = manifest.metadata or {}
        contract = metadata.get("resolved_contract")
        if isinstance(contract, dict):
            return contract
        return None

    def _academic_mode_enabled(self) -> bool:
        contract = self._resolved_contract_data()
        if contract is not None:
            clauses = contract.get("clauses")
            if isinstance(clauses, list) and "academic_mode" in clauses:
                return True
            return contract.get("execution_mode") == "academic"

        return bool(getattr(self._config.pipeline, "academic_mode", False))

    def _visualization_required(self) -> bool:
        contract = self._resolved_contract_data()
        if contract is not None:
            return bool(contract.get("visualization_required", False))

        manifest = self.runtime_prompt_manifest
        if manifest is None:
            return False
        prompt_manifest = manifest.prompt_manifest
        return bool(prompt_manifest.output_constraints.get("visualization_required", False))

    def _sandbox_enabled(self) -> bool:
        if self._resolved_contract_data() is not None:
            return self._visualization_required()
        return bool(getattr(self._config.pipeline, "academic_mode", False))

    def _contract_drift_issues(self) -> List[str]:
        manifest = self.runtime_prompt_manifest
        if manifest is None:
            return []

        metadata = manifest.metadata or {}
        contract_data = metadata.get("resolved_contract")
        if not isinstance(contract_data, dict):
            return []

        try:
            from academic_pe.contracts.drift import run_all as run_contract_drift_checks
            from academic_pe.contracts.models import ArtifactContract

            result = run_contract_drift_checks(ArtifactContract(**contract_data), self.context)
        except Exception as exc:
            logger.warning("Contract drift checks skipped: %s", exc)
            return []

        return result.issues

    def _log_quality_evaluations(self, qg_result, drift_issues: List[str]) -> None:
        try:
            qg_eval = Evaluation(
                run_id=self.run_id,
                eval_type="quality_gate",
                status="passed" if qg_result.passed else "failed",
                summary="; ".join(qg_result.issues) if qg_result.issues else "all checks passed",
                result_path=None,
                metadata_json=json.dumps({
                    "enabled_gates": {
                        "volume": self._config.quality_gate.volume.enabled,
                        "latex": self._config.quality_gate.latex.enabled,
                        "markdown": self._config.quality_gate.markdown.enabled,
                        "evidence": self._config.quality_gate.evidence.enabled,
                    }
                }, ensure_ascii=False),
                created_at=datetime.now().isoformat()
            )
            self._registry_store.add_evaluation(qg_eval)
        except Exception as e:
            logger.warning("Failed to register quality gate evaluation: %s", e)

        try:
            drift_eval = Evaluation(
                run_id=self.run_id,
                eval_type="contract_drift",
                status="failed" if drift_issues else "passed",
                summary="; ".join(drift_issues) if drift_issues else "no drift issues detected",
                result_path=None,
                metadata_json=None,
                created_at=datetime.now().isoformat()
            )
            self._registry_store.add_evaluation(drift_eval)
        except Exception as e:
            logger.warning("Failed to register contract drift evaluation: %s", e)

    @property
    def state(self) -> PipelineState:
        return self._state

    @property
    def previous_state(self) -> Optional[PipelineState]:
        return self._state_history[-1] if self._state_history else None

    @property
    def calculation_ledger(self) -> CalculationLedger:
        """Expose registered calculations for integrations that produce numeric evidence."""
        return self._calculation_ledger

    def register_calculation(self, entry: CalculationEntry | Mapping[str, Any]) -> CalculationEntry:
        """Register a deterministic calculation before the quality gate runs."""
        return self._calculation_ledger.register(entry)

    def _record_sandbox_calculations(
        self,
        entries: list[CalculationEntry],
        section_name: str,
    ) -> None:
        invalid_owners = [entry.calculation_id for entry in entries if entry.section_owner != section_name]
        if invalid_owners:
            raise PipelineError(
                "Sandbox calculation entries must belong to their generated section: "
                + ", ".join(invalid_owners)
            )
        if entries:
            self._calculation_ledger.upsert_many_for_section(section_name, entries)

    def _execute_sandbox_for_section(self, content: str, section_name: str) -> str:
        from academic_pe.core.sandbox import execute_sandbox_blocks_with_metadata

        result = execute_sandbox_blocks_with_metadata(content)
        self._record_sandbox_calculations(result.calculation_entries, section_name)
        return result.text

    def _register_curated_research_claims(self) -> None:
        curation = getattr(self._researcher, "last_curation", None)
        if curation is None:
            return
        sources_by_url = {
            (source.url or "").rstrip("/"): source.source_id
            for source in self._document_ledger.sources
            if source.url
        }
        for claim in curation.claims:
            source_ids = [
                sources_by_url[url.rstrip("/")]
                for url in claim.source_urls
                if url.rstrip("/") in sources_by_url
            ]
            status = claim.status if source_ids else "unsupported"
            if status not in {"supported", "assumption", "disputed", "unsupported"}:
                status = "unsupported"
            self._document_ledger.register_claim(
                text=claim.text,
                source_ids=source_ids,
                status=status,
                section_owner=claim.section_owner,
            )

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

    def _clean_section_content(self, content: str) -> str:
        return normalize_generated_text(strip_markdown_fences(content))

    def _register_section_metadata(self, section_name: str, content: str) -> None:
        import hashlib
        
        # Calculate sha256 of content
        content_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
        char_count = len(content)
        
        # Find section config in template or pipeline config
        title = None
        semantic_role = None
        heading_policy = None
        order_index = None
        
        # Check runtime template sections first
        sections_list = []
        if self.runtime_template and hasattr(self.runtime_template, "sections"):
            sections_list = self.runtime_template.sections
        else:
            sections_list = self._config.pipeline.sections
            
        for idx, sec in enumerate(sections_list):
            name_val = sec.get("name") if isinstance(sec, dict) else getattr(sec, "name", None)
            if name_val == section_name:
                if isinstance(sec, dict):
                    title = sec.get("title") or sec.get("topic")
                    semantic_role = sec.get("semantic_role", "body")
                    heading_policy = sec.get("heading_policy", "render_required")
                else:
                    title = getattr(sec, "title", getattr(sec, "topic", None))
                    semantic_role = getattr(sec, "semantic_role", "body")
                    heading_policy = getattr(sec, "heading_policy", "render_required")
                order_index = idx
                break
                
        # Register in SQLite
        section_record = Section(
            run_id=self.run_id,
            name=section_name,
            title=title,
            semantic_role=semantic_role,
            heading_policy=heading_policy,
            char_count=char_count,
            order_index=order_index,
            content_path=None,
            content_sha256=content_sha256,
            metadata_json=None
        )
        try:
            self._registry_store.add_section(section_record)
        except Exception as e:
            logger.warning("Failed to register section %s in SQLite: %s", section_name, e)

    def _set_section_content(self, section_name: str, content: str) -> None:
        cleaned_content = self._clean_section_content(content)
        self.context[section_name] = cleaned_content
        self._emit_section_delta(section_name, cleaned_content, cleaned_content)
        self._register_section_metadata(section_name, cleaned_content)

    def _capture_self_critique_summary(
        self,
        agent: BaseAgent,
        *,
        stage: str,
        section_name: Optional[str] = None,
    ) -> None:
        summary = getattr(agent, "last_self_critique_summary", None)
        if not summary:
            return
        entry = {
            "agent": getattr(agent.config, "role", "agent"),
            "stage": stage,
            "summary": str(summary),
        }
        if section_name:
            entry["section"] = section_name
        self.self_critique_summaries.append(entry)
        agent.last_self_critique_summary = None

    def _document_memory(self, current_section_name: str = "", with_line_numbers: bool = False) -> str:
        parts: List[str] = []
        evidence_context = self._document_ledger.writer_context()
        if evidence_context:
            parts.append(
                "[Verified Evidence Ledger]\n"
                + evidence_context
                + "\nUse only these source IDs/URLs for external claims; do not invent sources or claims."
            )
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

    def _merge_edit_plan(self) -> Optional[EditPlan]:
        metadata = self._runtime_metadata()
        raw_plan = metadata.get("edit_plan")
        if not isinstance(raw_plan, dict):
            return None
        try:
            return EditPlan.model_validate(raw_plan)
        except Exception as exc:
            logger.warning("Continuation edit plan metadata is invalid; falling back to section drafting: %s", exc)
            return None

    def _runtime_metadata(self) -> Dict[str, Any]:
        if self.runtime_prompt_manifest is not None:
            return dict(self.runtime_prompt_manifest.metadata or {})
        if self.runtime_template is not None:
            return dict(self.runtime_template.metadata or {})
        return {}

    def _draft_with_merge_operations(self, target_language: str) -> bool:
        if not self.continuation_source:
            return False

        edit_plan = self._merge_edit_plan()
        if edit_plan is None:
            return False

        document_state = extract_document_state(self.continuation_source)
        if not document_state.source_sections:
            logger.info("Continuation merge flow skipped: no source sections extracted.")
            return False

        task = render_template(
            DEFAULT_MERGE_OPERATION_TEMPLATE,
            {
                "language": target_language,
                "language_instruction": language_instruction(target_language),
                "user_topic": self.user_topic,
                "user_instructions": self.user_instructions,
                "edit_plan_json": json.dumps(edit_plan.model_dump(mode="json"), ensure_ascii=False, indent=2),
                "document_state_json": json.dumps(document_state.model_dump(mode="json"), ensure_ascii=False, indent=2),
            },
        )
        raw_payload = self._writer.process(
            task,
            context=self._continuation_context(),
            document_sections=self.context,
        )
        self._capture_self_critique_summary(self._writer, stage="merge_operation_payload", section_name="merge_patch")

        try:
            payload = parse_merge_operation_payload(raw_payload)
        except Exception as exc:
            logger.warning(
                "Writer did not return a valid merge-operation payload; falling back to section drafting. Raw preview: %r. Error: %s",
                compact_log_preview(raw_payload),
                exc,
            )
            return False

        operations = payload.operations or edit_plan.operations
        missing_roles = [
            role
            for role in required_content_roles(operations)
            if not payload.operation_outputs.get(role, "").strip()
        ]
        if missing_roles:
            logger.warning(
                "Writer merge-operation payload is missing required content roles %s; falling back to section drafting.",
                missing_roles,
            )
            return False

        target_issues = validate_merge_operation_targets(document_state, operations)
        if target_issues:
            logger.warning(
                "Writer merge-operation payload has invalid operation targets %s; falling back to section drafting.",
                target_issues,
            )
            return False

        merge_patch = apply_merge_operations(
            document_state,
            operations,
            payload.operation_outputs,
        )
        if payload.reviewer_notes:
            merge_patch.reviewer_notes.extend(payload.reviewer_notes)

        self._store_merge_patch_metadata(compact_merge_patch_metadata(merge_patch))
        self._sync_sections_to_context_order(merge_patch.assembled_context)
        for section_name, content in merge_patch.assembled_context.items():
            self._set_section_content(section_name, content)

        logger.info(
            "Continuation merge flow assembled %d section(s) using %d operation(s).",
            len(merge_patch.assembled_context),
            len(operations),
        )
        return True

    def _store_merge_patch_metadata(self, merge_patch_metadata: dict) -> None:
        if self.runtime_template is not None:
            metadata = dict(self.runtime_template.metadata or {})
            metadata["merge_patch"] = merge_patch_metadata
            self.runtime_template = self.runtime_template.model_copy(update={"metadata": metadata})
        if self.runtime_prompt_manifest is not None:
            metadata = dict(self.runtime_prompt_manifest.metadata or {})
            metadata["merge_patch"] = merge_patch_metadata
            self.runtime_prompt_manifest = self.runtime_prompt_manifest.model_copy(update={"metadata": metadata})

    def _sync_sections_to_context_order(self, assembled_context: Dict[str, str]) -> None:
        section_names = [name for name in assembled_context if name != "document_plan"]
        existing_config_sections = {section.name: section for section in self._config.pipeline.sections}
        existing_template_sections = {}
        internal_template_sections: List[TemplateSection] = []
        if self.runtime_template is not None:
            for section in self.runtime_template.sections:
                existing_template_sections[section.name] = section
                if getattr(section.heading_policy, "value", section.heading_policy) == "internal_only":
                    internal_template_sections.append(section)

        resolved_config_sections: List[SectionPrompt] = []
        resolved_template_sections: List[TemplateSection] = []
        for name in section_names:
            default_title = _section_title_from_content(name, assembled_context.get(name, ""))
            template_section = existing_template_sections.get(name) or TemplateSection(
                name=name,
                title=default_title,
                topic=default_title,
                instruction="Merged continuation content.",
                semantic_role="body",
                heading_policy="render_allowed",
            )
            resolved_template_sections.append(template_section)
            resolved_config_sections.append(
                existing_config_sections.get(name)
                or template_section_to_section_prompt(template_section)
            )

        self._config.pipeline.sections = resolved_config_sections
        if self.runtime_template is not None:
            preserved_internal = [
                section for section in internal_template_sections
                if section.name not in {item.name for item in resolved_template_sections}
            ]
            self.runtime_template = self.runtime_template.model_copy(
                update={"sections": [*resolved_template_sections, *preserved_internal]}
            )

    def _ensure_drafted_content_exists(self) -> None:
        exportable_sections = {
            name: content
            for name, content in self.context.items()
            if name != "document_plan" and isinstance(content, str) and content.strip()
        }
        if exportable_sections:
            return

        configured_sections = [section.name for section in self._config.pipeline.sections]
        raise PipelineError(
            "Drafting produced no exportable document sections. "
            f"Configured draft sections: {configured_sections or 'none'}. "
            "The pipeline cannot treat the internal document plan as the final artifact."
        )

    def run_pipeline(self, render_artifact: bool = True) -> str:
        logger.info("Pipeline started.")
        
        # Register run in SQLite Registry
        from datetime import datetime
        import json
        
        pipeline_mode = "standard"
        if self.continuation_source:
            pipeline_mode = "continuation"
        elif self.web_search_enabled:
            pipeline_mode = "research"
            
        run_metadata = {
            "academic_mode": self._academic_mode_enabled(),
            "template_mode": self._config.pipeline.template_mode.value,
            "template_id": self._config.pipeline.template_id,
        }
        
        run_kind = "smoke" if self.run_id and (self.run_id.startswith("smoke_") or self.run_id.startswith("quality_") or self.run_id.startswith("test_")) else "generation"
        run_record = Run(
            run_id=self.run_id,
            kind=run_kind,
            status="running",
            topic=self.user_topic or "Unknown",
            instructions_preview=self.user_instructions,
            pipeline_mode=pipeline_mode,
            web_search_enabled=self.web_search_enabled,
            created_at=datetime.now().isoformat(),
            started_at=datetime.now().isoformat(),
            output_dir=self._config.pipeline.output_dir,
            metadata_json=json.dumps(run_metadata, ensure_ascii=False)
        )
        try:
            self._registry_store.create_run(run_record)
        except Exception as e:
            logger.warning("Failed to create run in SQLite Registry: %s", e)
            
        # Register agents
        for role, agent_obj in [
            ("writer", self._writer),
            ("reviewer", self._reviewer),
            ("planner", self._planner if self._has_dedicated_planner else None),
            ("researcher", self._researcher),
        ]:
            if agent_obj is not None:
                agent_cfg = self._config.agents.get(role)
                if agent_cfg:
                    provider = getattr(agent_cfg.provider, "value", agent_cfg.provider)
                    self_critique_enabled = getattr(agent_cfg.self_critique, "enabled", False)
                    agent_record = RunAgent(
                        run_id=self.run_id,
                        role=role,
                        provider=provider,
                        model=agent_cfg.model,
                        temperature=agent_cfg.temperature,
                        agent_type=agent_cfg.agent_type,
                        self_critique_enabled=self_critique_enabled,
                        metadata_json=None
                    )
                    try:
                        self._registry_store.add_agent(agent_record)
                    except Exception as e:
                        logger.warning("Failed to register agent %s in SQLite Registry: %s", role, e)
                        
        # Register snapshots
        if self.runtime_template:
            try:
                self._registry_store.add_runtime_snapshot(RuntimeSnapshot(
                    run_id=self.run_id,
                    snapshot_type="runtime_template",
                    metadata_json=json.dumps(self.runtime_template.model_dump(mode="json"), ensure_ascii=False)
                ))
            except Exception as e:
                logger.warning("Failed to register runtime_template snapshot: %s", e)
        if self.runtime_prompt_manifest:
            try:
                self._registry_store.add_runtime_snapshot(RuntimeSnapshot(
                    run_id=self.run_id,
                    snapshot_type="runtime_prompt_manifest",
                    metadata_json=json.dumps(self.runtime_prompt_manifest.model_dump(mode="json"), ensure_ascii=False)
                ))
            except Exception as e:
                logger.warning("Failed to register runtime_prompt_manifest snapshot: %s", e)

        # Register continuation source and reference materials
        try:
            attachments_dir = os.path.join(self._config.pipeline.output_dir, "attachments")
            
            import hashlib
            def get_content_info(text: str):
                content_bytes = text.encode("utf-8", errors="replace")
                size_bytes = len(content_bytes)
                sha256 = hashlib.sha256(content_bytes).hexdigest()
                return size_bytes, sha256

            def save_attachment_file(filename: str, content: str) -> str:
                os.makedirs(attachments_dir, exist_ok=True)
                safe_filename = os.path.basename(filename)
                original_ext = os.path.splitext(safe_filename)[1].lower()
                dest_filename = safe_filename
                if original_ext in {".pdf", ".docx"}:
                    dest_filename = safe_filename + ".txt"
                
                dest_path = os.path.join(attachments_dir, dest_filename)
                with open(dest_path, "w", encoding="utf-8") as f:
                    f.write(content)
                return dest_path

            if self.continuation_source:
                content = self.continuation_source.get("content")
                filename = self.continuation_source.get("filename")
                
                size_bytes, sha256 = None, None
                path = None
                if content and filename:
                    try:
                        path = save_attachment_file(filename, content)
                        size_bytes, sha256 = get_content_info(content)
                    except Exception as e:
                        logger.warning("Failed to save continuation source file: %s", e)
                
                metadata_id = self.continuation_source.get("metadata_id") or self.continuation_source.get("run_id")
                
                source_record = Source(
                    run_id=self.run_id,
                    source_type="continuation",
                    title=self.continuation_source.get("topic") or filename or "Continuation Source",
                    url=None,
                    path=path or metadata_id,
                    sha256=sha256,
                    used_by="planner,writer",
                    metadata_json=json.dumps({
                        "intent_override": self.continuation_source.get("intent_override"),
                        "token_count": self.continuation_source.get("token_count"),
                    }, ensure_ascii=False)
                )
                try:
                    self._registry_store.add_source(source_record)
                except Exception as e:
                    logger.warning("Failed to register continuation source: %s", e)
                    
                if path:
                    from academic_pe.core.registry.importers import safe_relative_path
                    rel_path = safe_relative_path(path)
                    artifact_record = Artifact(
                        run_id=self.run_id,
                        artifact_type="ocr_output" if (filename or "").lower().endswith((".pdf", ".docx")) else "markdown",
                        path=os.path.abspath(path),
                        relative_path=rel_path,
                        filename=os.path.basename(path),
                        mime_type="text/plain",
                        size_bytes=size_bytes,
                        sha256=sha256,
                        created_at=datetime.now().isoformat(),
                        is_diagnostic=False
                    )
                    try:
                        self._registry_store.add_artifact(artifact_record)
                    except Exception as e:
                        logger.warning("Failed to register continuation source artifact: %s", e)

            for item in self.reference_materials:
                filename = item.get("filename")
                content = item.get("content")
                if not filename or not content:
                    continue
                    
                size_bytes, sha256 = get_content_info(content)
                path = None
                try:
                    path = save_attachment_file(filename, content)
                except Exception as e:
                    logger.warning("Failed to save reference material file: %s", e)
                    
                orig_ext = os.path.splitext(filename)[1].lower()
                source_type = "ocr" if orig_ext in {".pdf", ".docx"} else "manual_reference"
                
                source_record = Source(
                    run_id=self.run_id,
                    source_type=source_type,
                    title=filename,
                    url=None,
                    path=path,
                    sha256=sha256,
                    used_by="planner,writer",
                    metadata_json=json.dumps({
                        "token_count": item.get("token_count")
                    }, ensure_ascii=False)
                )
                try:
                    self._registry_store.add_source(source_record)
                except Exception as e:
                    logger.warning("Failed to register reference source: %s", e)
                    
                if path:
                    from academic_pe.core.registry.importers import safe_relative_path
                    rel_path = safe_relative_path(path)
                    artifact_record = Artifact(
                        run_id=self.run_id,
                        artifact_type="ocr_output" if orig_ext in {".pdf", ".docx"} else "markdown",
                        path=os.path.abspath(path),
                        relative_path=rel_path,
                        filename=os.path.basename(path),
                        mime_type="text/plain",
                        size_bytes=size_bytes,
                        sha256=sha256,
                        created_at=datetime.now().isoformat(),
                        is_diagnostic=False
                    )
                    try:
                        self._registry_store.add_artifact(artifact_record)
                    except Exception as e:
                        logger.warning("Failed to register reference artifact: %s", e)
        except Exception as e:
            logger.warning("Best-effort attachment registration failed: %s", e)

        output_path = "(no output)"
        raw_language_policy = getattr(self._config.pipeline, "language", "auto")
        language_policy = getattr(raw_language_policy, "value", raw_language_policy)
        prompt_text = " ".join(x for x in [self.user_topic, self.user_instructions] if x)
        target_language = resolve_output_language(prompt_text, str(language_policy))

        try:
            # --- PLANNING ---
            self.transition_to(PipelineState.PLANNING)
            if self.web_search_enabled:
                if not self._has_dedicated_planner:
                    raise PipelineError(
                        "Web search requires a dedicated planner agent. Configure agents.planner "
                        "or disable web_search_enabled so the writer is not used as a research planner."
                    )
                if self._researcher is None:
                    raise PipelineError(
                        "Web search requires a dedicated researcher agent. Configure agents.researcher "
                        "or disable web_search_enabled."
                    )
                logger.info("[Researcher] Spawning search agent: Generating research queries...")
                queries = self._generate_search_queries()
                logger.info(f"[Researcher] Generated queries: {queries}")
                if queries:
                    run_dir = self._config.pipeline.output_dir
                    logger.info("[Researcher] Spawning parallel search agents to retrieve search results...")
                    from typing import cast
                    from academic_pe.agents.researcher import ResearcherAgent
                    researcher_agent = cast(ResearcherAgent, self._researcher)
                    self.search_findings = researcher_agent.run_research(queries, run_dir)
                    self.search_findings = normalize_generated_text(self.search_findings)
                    logger.info("[Researcher] Parallel search completed. Sourcing findings...")

                    # Scan and register web research logs and crawled sources
                    try:
                        research_dir = os.path.join(run_dir, "research")
                        if os.path.exists(research_dir):
                            for filename in os.listdir(research_dir):
                                if filename.startswith("query_") and filename.endswith(".json"):
                                    filepath = os.path.join(research_dir, filename)
                                    # 1. Read research query JSON
                                    with open(filepath, "r", encoding="utf-8") as f:
                                        data = json.load(f)
                                    
                                    query_text = data.get("query", "")
                                    results = data.get("results", [])
                                    
                                    # Compute file checksum & size
                                    with open(filepath, "rb") as f:
                                        file_bytes = f.read()
                                    file_sha256 = hashlib.sha256(file_bytes).hexdigest()
                                    file_size = len(file_bytes)
                                    
                                    # 2. Register file as diagnostic Artifact
                                    from academic_pe.core.registry.importers import safe_relative_path
                                    rel_path = safe_relative_path(filepath)
                                    
                                    artifact_record = Artifact(
                                        run_id=self.run_id,
                                        artifact_type="research_log",
                                        path=os.path.abspath(filepath),
                                        relative_path=rel_path,
                                        filename=filename,
                                        mime_type="application/json",
                                        size_bytes=file_size,
                                        sha256=file_sha256,
                                        created_at=datetime.now().isoformat(),
                                        is_diagnostic=True
                                    )
                                    try:
                                        self._registry_store.add_artifact(artifact_record)
                                    except Exception as e:
                                        logger.warning("Failed to register research log artifact: %s", e)
                                        
                                    # 3. Register each webpage crawled in results as a Source
                                    for res in results:
                                        title = res.get("title", "")
                                        url = res.get("url", "")
                                        snippet = res.get("snippet", "")
                                        content = res.get("content", "")
                                        
                                        content_bytes = content.encode("utf-8", errors="replace")
                                        content_sha256 = hashlib.sha256(content_bytes).hexdigest()
                                        
                                        source_record = Source(
                                            run_id=self.run_id,
                                            source_type="web",
                                            title=title,
                                            url=url,
                                            path=None,
                                            sha256=content_sha256,
                                            used_by="researcher",
                                            metadata_json=json.dumps({
                                                "query": query_text,
                                                "snippet": snippet
                                            }, ensure_ascii=False)
                                        )
                                        try:
                                            self._registry_store.add_source(source_record)
                                        except Exception as e:
                                            logger.warning("Failed to register web research source: %s", e)
                                        self._document_ledger.register_source(
                                            title=title or url,
                                            url=url or None,
                                            source_type="web",
                                            reliability="unverified",
                                            notes=[f"query={query_text}"] if query_text else [],
                                        )
                        self._register_curated_research_claims()
                    except Exception as e:
                        logger.warning("Best-effort research log registration failed: %s", e)

            plan_task = render_template(
                DEFAULT_PLAN_TEMPLATE,
                {
                    "sections": self._config.pipeline.sections,
                    "language": target_language,
                    "language_instruction": language_instruction(target_language),
                    "user_topic": self.user_topic,
                    "user_instructions": self.user_instructions,
                    "continuation_context": self._continuation_context(),
                    "academic_mode": self._academic_mode_enabled(),
                    "visualization_required": self._visualization_required(),
                    "output_dir": self._config.pipeline.output_dir,
                    "reference_materials": self.reference_materials,
                    "search_findings": self.search_findings,
                },
            )
            logger.info("Creating document plan before drafting sections.")
            self._draft_plan = self._planner.process(plan_task)
            self._draft_plan = self._clean_section_content(self._draft_plan)
            self._capture_self_critique_summary(self._planner, stage="planning", section_name="document_plan")
            self._set_section_content("document_plan", self._draft_plan)

            # --- DRAFTING ---
            self.transition_to(PipelineState.DRAFTING)

            if not self._draft_with_merge_operations(target_language):
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
                            "academic_mode": self._academic_mode_enabled(),
                            "visualization_required": self._visualization_required(),
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
                        self._capture_self_critique_summary(self._writer, stage="drafting", section_name=section.name)

                        if self._sandbox_enabled():
                            try:
                                draft_content = self._execute_sandbox_for_section(draft_content, section.name)
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

                    draft_content = self._clean_section_content(draft_content)
                    if target_language == "ru" and not has_cyrillic(draft_content):
                        logger.info("Translating section %s to Russian...", section.name)
                        draft_content = translate_markdown_to_ru(draft_content)
                    self._set_section_content(section.name, draft_content)

            self._ensure_drafted_content_exists()

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
                qg_result = run_quality_gate(
                    self.context,
                    self._config.quality_gate,
                    document_state=self._runtime_metadata().get("document_state"),
                    ledger=self._document_ledger,
                    calculation_ledger=self._calculation_ledger,
                )
                drift_issues = self._contract_drift_issues()
                self._log_quality_evaluations(qg_result, drift_issues)

                if not qg_result.passed:
                    # Quality gate failed, bypass LLM reviewer and auto-generate rejection
                    logger.warning("Quality Gate failed during review loop: %s", qg_result.issues)
                    critique = "REJECTED\n" + "\n".join(
                        _quality_gate_review_issue(issue)
                        for issue in qg_result.issues
                    )
                elif drift_issues:
                    logger.warning("Contract drift checks failed during review loop: %s", drift_issues)
                    critique = "REJECTED\n" + "\n".join(f"- [general]: Contract Drift issue: {issue}" for issue in drift_issues)
                else:
                    critique = self._reviewer.process(
                        render_template(
                            DEFAULT_REVIEW_TEMPLATE,
                            {
                                "language": target_language,
                                "review_focus": review_focus,
                                "sections": self._config.pipeline.sections,
                                "continuation_context": self._continuation_context(),
                                "academic_mode": self._academic_mode_enabled(),
                                "visualization_required": self._visualization_required(),
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
                                "academic_mode": self._academic_mode_enabled(),
                                "visualization_required": self._visualization_required(),
                                "output_dir": self._config.pipeline.output_dir,
                            },
                        )
                        current_content = self.context.get(section.name, "")
                        patch_text = self._writer.process(
                            task,
                            context=self._document_memory(section.name, with_line_numbers=True),
                            document_sections=self.context,
                        )
                        self._capture_self_critique_summary(self._writer, stage="patch_revision", section_name=section.name)
                        revised_content = current_content
                        try:
                            revised_content = apply_line_replace_patch(current_content, patch_text)
                            revised_content = strip_markdown_fences(revised_content)
                            revised_content = isolate_current_section_revision(
                                revised_content,
                                section,
                                self._config.pipeline.sections,
                            )
                            if self._sandbox_enabled():
                                revised_content = self._execute_sandbox_for_section(revised_content, section.name)
                        except Exception as exc:
                            logger.warning(
                                "Patch revision failed for section %s: %s. Falling back to full-section revision. Raw patch preview: %r",
                                section.name,
                                exc,
                                compact_log_preview(patch_text),
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
                                    "academic_mode": self._academic_mode_enabled(),
                                    "visualization_required": self._visualization_required(),
                                    "output_dir": self._config.pipeline.output_dir,
                                },
                            )
                            for fallback_attempt in range(max_sandbox_retries):
                                self._check_cancelled()
                                current_fallback_task = fallback_task
                                if error_feedback:
                                    current_fallback_task += f"\n\n[Revision Feedback]\nYour previous response could not be accepted. {error_feedback}"

                                revised_content = self._writer.process(
                                    current_fallback_task,
                                    context=self._document_memory(section.name),
                                    document_sections=self.context,
                                )
                                self._capture_self_critique_summary(self._writer, stage="fallback_revision", section_name=section.name)
                                revised_content = strip_markdown_fences(revised_content)
                                try:
                                    revised_content = isolate_current_section_revision(
                                        revised_content,
                                        section,
                                        self._config.pipeline.sections,
                                    )
                                except SectionPatchError as scope_exc:
                                    logger.warning(
                                        "Fallback revision for section %s returned invalid section scope (attempt %d/%d): %s",
                                        section.name,
                                        fallback_attempt + 1,
                                        max_sandbox_retries,
                                        scope_exc,
                                    )
                                    if fallback_attempt == max_sandbox_retries - 1:
                                        raise PipelineError(
                                            f"Fallback revision for section {section.name} did not return a single section: {scope_exc}"
                                        ) from scope_exc
                                    error_feedback = f"{scope_exc} Other sections in context are read-only; return only section '{section.name}'."
                                    continue

                                if self._sandbox_enabled():
                                    try:
                                        revised_content = self._execute_sandbox_for_section(revised_content, section.name)
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
                    if reason:
                        logger.info("Starting writer self-verification against current reviewer feedback...")
                        verify_reasons_by_section = parse_rejection_reasons(
                            reason, self._config.pipeline.sections
                        )
                        for section in self._config.pipeline.sections:
                            self._check_cancelled()
                            sec_verify_reason = verify_reasons_by_section.get(section.name, reason)
                            verified = False
                            verify_scope_feedback = ""
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
                                        "academic_mode": self._academic_mode_enabled(),
                                        "visualization_required": self._visualization_required(),
                                        "output_dir": self._config.pipeline.output_dir,
                                    }
                                )
                                if verify_scope_feedback:
                                    verify_task += f"\n\n[Revision Scope Feedback]\nYour previous response could not be accepted. {verify_scope_feedback}"
                                response = self._writer.process(
                                    verify_task,
                                    context=self._document_memory(section.name),
                                    document_sections=self.context,
                                )
                                self._capture_self_critique_summary(self._writer, stage="self_verification", section_name=section.name)
                                if response.strip() == "VERIFIED":
                                    logger.info("Section %s verified successfully.", section.name)
                                    verified = True
                                    break
                                else:
                                    logger.warning(
                                        "Section %s verification failed. Writer corrected the text (attempt %d/2).",
                                        section.name, verify_attempt + 1
                                    )
                                    try:
                                        response = isolate_current_section_revision(
                                            response,
                                            section,
                                            self._config.pipeline.sections,
                                        )
                                    except SectionPatchError as scope_exc:
                                        logger.warning(
                                            "Self-verification for section %s returned invalid section scope (attempt %d/2): %s",
                                            section.name,
                                            verify_attempt + 1,
                                            scope_exc,
                                        )
                                        if verify_attempt == 1:
                                            raise PipelineError(
                                                f"Self-verification for section {section.name} did not return a single section: {scope_exc}"
                                            ) from scope_exc
                                        verify_scope_feedback = f"{scope_exc} Other sections in context are read-only; return only section '{section.name}'."
                                        continue
                                    if self._sandbox_enabled():
                                        try:
                                            response = self._execute_sandbox_for_section(response, section.name)
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
            qg_result = run_quality_gate(
                self.context,
                self._config.quality_gate,
                document_state=self._runtime_metadata().get("document_state"),
                ledger=self._document_ledger,
                calculation_ledger=self._calculation_ledger,
            )
            drift_issues = self._contract_drift_issues()
            self._log_quality_evaluations(qg_result, drift_issues)

            if not qg_result.passed:
                for issue in qg_result.issues:
                    logger.warning("Quality Gate: %s", issue)
                raise PipelineError(
                    f"Quality Gate failed with {len(qg_result.issues)} issue(s). "
                    + "; ".join(qg_result.issues)
                )
            if drift_issues:
                for issue in drift_issues:
                    logger.warning("Contract Drift: %s", issue)
                raise PipelineError(
                    f"Contract Drift failed with {len(drift_issues)} issue(s). "
                    + "; ".join(drift_issues)
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
            
            try:
                self._registry_store.update_run_status(
                    run_id=self.run_id,
                    status="succeeded",
                    finished_at=datetime.now().isoformat()
                )
            except Exception as e:
                logger.warning("Failed to update status in SQLite Registry: %s", e)
                
            return output_path

        except PipelineCancelled:
            self._state = PipelineState.FAILED
            try:
                self._registry_store.update_run_status(
                    run_id=self.run_id,
                    status="cancelled",
                    finished_at=datetime.now().isoformat()
                )
            except Exception as e:
                logger.warning("Failed to update status in SQLite Registry: %s", e)
            raise
        except PipelineError as e:
            try:
                self._registry_store.update_run_status(
                    run_id=self.run_id,
                    status="failed",
                    error_type=type(e).__name__,
                    error_message=str(e),
                    finished_at=datetime.now().isoformat()
                )
            except Exception as ree:
                logger.warning("Failed to update status in SQLite Registry: %s", ree)
            raise
        except Exception as e:
            logger.exception("Pipeline failed at state %s", self._state.name)
            self._state = PipelineState.FAILED
            try:
                self._registry_store.update_run_status(
                    run_id=self.run_id,
                    status="failed",
                    error_type=type(e).__name__,
                    error_message=str(e),
                    finished_at=datetime.now().isoformat()
                )
            except Exception as ree:
                logger.warning("Failed to update status in SQLite Registry: %s", ree)
            raise PipelineError(
                f"Pipeline failed at {self._state.name}. Check logs for details."
            ) from None


def _apply_runtime_template(
    config: AppConfig,
    runtime_template: RuntimeTemplate,
) -> AppConfig:
    resolved_config = config.model_copy(deep=True)
    runtime_template = _ensure_runtime_template_has_draft_sections(runtime_template)
    resolved_config.pipeline.sections = [
        template_section_to_section_prompt(section)
        for section in renderable_sections(runtime_template.sections)
    ]
    return resolved_config


def _ensure_runtime_template_has_draft_sections(runtime_template: RuntimeTemplate) -> RuntimeTemplate:
    if any(is_renderable_section(section) for section in runtime_template.sections):
        return runtime_template

    promoted_sections: List[TemplateSection] = []
    promoted = False
    for section in runtime_template.sections:
        if section.semantic_role in {
            SemanticRole.body.value,
            SemanticRole.chapter.value,
            SemanticRole.academic_section.value,
            SemanticRole.narrative_beat.value,
        }:
            promoted_sections.append(
                section.model_copy(update={"heading_policy": HeadingPolicy.render_allowed})
            )
            promoted = True
        else:
            promoted_sections.append(section)

    if not promoted:
        raise PipelineError("Runtime template has no renderable draft sections.")

    logger.warning(
        "Runtime template had no renderable sections; promoted %d writing section(s) to render_allowed.",
        len([section for section in promoted_sections if is_renderable_section(section)]),
    )
    return runtime_template.model_copy(update={"sections": promoted_sections})


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

    prompt = f"""You are an artifact-aware editor.
Your task is to refine the document topic into a clear, suitable, and artifact-appropriate title or brief.

User Topic: "{topic}"
User Instructions/Constraints: "{instructions or '(none)'}"

Rules:
1. If the User Instructions explicitly state that the topic/title must not be changed, must remain exactly as is, or must not be renamed (e.g. "не переименовывать тему", "do not rename", etc.), you MUST return the User Topic exactly as is.
2. Otherwise, write a more correct and stylistically refined title or brief that preserves the user's requested artifact type, genre, audience, voice, and constraints.
3. Do not turn creative, school-level, technical, plan, report, or freeform requests into academic papers.
4. The title must be in the same language as the User Topic.
5. Return ONLY the final title or brief. Do not include any explanations, quotes, or introductory text.
"""
    refined = writer_agent.process(prompt)
    return refined.strip().strip('"\'')


def create_orchestrator_from_config(
    config: AppConfig,
    renderer: Optional[Renderer] = None,
    template_selector: Optional[TemplateSelector] = None,
    prompt_manifest_resolver: Optional[PromptManifestResolver] = None,
    artifact_manifest_resolver: Optional[ArtifactManifestResolver] = None,
    user_topic: str = "",
    user_instructions: str = "",
    continuation_source: Optional[Dict[str, Any]] = None,
    artifact_override: Optional[str] = None,
    reference_materials: Optional[List[Dict[str, Any]]] = None,
    web_search_enabled: bool = False,
    registry_store: Optional[RegistryStore] = None,
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
    runtime_prompt_manifest = _apply_artifact_manifest_metadata(
        runtime_prompt_manifest,
        config=config,
        topic=refined_topic,
        instructions=user_instructions,
        continuation_source=continuation_source,
        artifact_manifest_resolver=artifact_manifest_resolver,
        artifact_override=artifact_override,
    )
    runtime_template, runtime_prompt_manifest = _apply_continuation_editorial_metadata(
        runtime_template,
        runtime_prompt_manifest,
        topic=refined_topic,
        instructions=user_instructions,
        continuation_source=continuation_source,
    )
    runtime_template = _ensure_runtime_template_has_draft_sections(runtime_template)
    resolved_config = _apply_runtime_template(config, runtime_template)
    
    # Set resolved config pipeline title to refined topic
    resolved_config.pipeline.title = refined_topic

    resolver = prompt_manifest_resolver or PromptManifestResolver()
    resolved_config = resolver.resolve_app_config(resolved_config, runtime_prompt_manifest)

    writer = create_agent("writer", resolved_config.agents["writer"], retry_cfg=resolved_config.retry)
    reviewer = None
    if "reviewer" in resolved_config.agents:
        reviewer = create_agent("reviewer", resolved_config.agents["reviewer"], retry_cfg=resolved_config.retry)
    planner = None
    if "planner" in resolved_config.agents:
        planner = create_agent("planner", resolved_config.agents["planner"], retry_cfg=resolved_config.retry)
    researcher = None
    if "researcher" in resolved_config.agents:
        researcher = create_agent("researcher", resolved_config.agents["researcher"], retry_cfg=resolved_config.retry)

    orchestrator = Orchestrator(
        writer=writer,
        reviewer=reviewer,
        planner=planner,
        researcher=researcher,
        config=resolved_config,
        renderer=renderer,
        runtime_template=runtime_template,
        runtime_prompt_manifest=runtime_prompt_manifest,
        continuation_source=continuation_source,
        reference_materials=reference_materials,
        web_search_enabled=web_search_enabled,
        registry_store=registry_store,
    )
    orchestrator.user_topic = refined_topic
    orchestrator.user_instructions = user_instructions
    return orchestrator


def _apply_artifact_manifest_metadata(
    runtime_prompt_manifest: RuntimePromptManifest,
    *,
    config: AppConfig,
    topic: str,
    instructions: str,
    continuation_source: Optional[Dict[str, Any]],
    artifact_manifest_resolver: Optional[ArtifactManifestResolver],
    artifact_override: Optional[str] = None,
) -> RuntimePromptManifest:
    resolver = artifact_manifest_resolver or ArtifactManifestResolver()
    try:
        resolved = resolver.resolve(
            topic=topic,
            instructions=instructions,
            execution_mode=_pipeline_execution_mode(config),
            language=str(getattr(getattr(config.pipeline, "language", "auto"), "value", getattr(config.pipeline, "language", "auto"))),
            mode="continuation" if continuation_source else "new",
            continuation_metadata=_continuation_manifest_metadata(continuation_source),
            artifact_override=artifact_override,
        )
    except Exception as exc:
        logger.warning("Artifact manifest resolution skipped: %s", exc)
        return runtime_prompt_manifest

    metadata = dict(runtime_prompt_manifest.metadata or {})
    metadata.update(resolved.metadata())
    return runtime_prompt_manifest.model_copy(update={"metadata": metadata})


def _apply_continuation_editorial_metadata(
    runtime_template: RuntimeTemplate,
    runtime_prompt_manifest: RuntimePromptManifest,
    *,
    topic: str,
    instructions: str,
    continuation_source: Optional[Dict[str, Any]],
) -> tuple[RuntimeTemplate, RuntimePromptManifest]:
    intent = infer_continuation_intent(
        topic=topic,
        instructions=instructions,
        continuation_source=continuation_source,
    )
    if intent is None:
        return runtime_template, runtime_prompt_manifest

    document_state_model = extract_document_state(continuation_source)
    terminal_sections = document_state_model.terminal_sections or detect_terminal_sections(continuation_source)
    document_state = _compact_document_state_metadata(document_state_model)
    edit_plan = build_default_edit_plan(intent.intent, terminal_sections).model_dump(mode="json")

    template_metadata = dict(runtime_template.metadata or {})
    template_metadata["continuation_intent"] = intent.to_dict()
    template_metadata["document_state"] = document_state
    template_metadata["edit_plan"] = edit_plan

    manifest_metadata = dict(runtime_prompt_manifest.metadata or {})
    manifest_metadata["continuation_intent"] = intent.to_dict()
    manifest_metadata["document_state"] = document_state
    manifest_metadata["edit_plan"] = edit_plan

    return (
        runtime_template.model_copy(update={"metadata": template_metadata}),
        runtime_prompt_manifest.model_copy(update={"metadata": manifest_metadata}),
    )


def _compact_document_state_metadata(document_state: Any) -> dict:
    data = document_state.model_dump(mode="json")
    data["rendered_body"] = {}
    for section in data.get("source_sections", []):
        if isinstance(section, dict):
            section.pop("content", None)
    return data


def _humanize_section_name(name: str) -> str:
    return re.sub(r"[_-]+", " ", name).strip().title()


def _first_markdown_heading(text: str) -> Optional[str]:
    if not text:
        return None
    match = re.search(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", text, flags=re.MULTILINE)
    if not match:
        return None
    heading = re.sub(r"[*_`]+", "", match.group(1)).strip()
    return heading or None


def _section_title_from_content(name: str, content: str) -> str:
    if name == "continuation":
        heading = _first_markdown_heading(content)
        if heading:
            return heading
    return _humanize_section_name(name)


def _pipeline_execution_mode(config: AppConfig) -> str:
    return "academic" if getattr(config.pipeline, "academic_mode", False) else "standard"


def _continuation_manifest_metadata(continuation_source: Optional[Dict[str, Any]]) -> Optional[dict]:
    if not continuation_source:
        return None

    top_level_metadata = {
        key: continuation_source[key]
        for key in [
            "resolved_manifest",
            "resolved_contract",
            "contract_sexpr",
            "manifest_selection",
            "decision_summary",
        ]
        if key in continuation_source
    }
    if top_level_metadata:
        return top_level_metadata

    runtime_prompt_manifest = continuation_source.get("runtime_prompt_manifest")
    if isinstance(runtime_prompt_manifest, dict):
        metadata = runtime_prompt_manifest.get("metadata")
        if isinstance(metadata, dict):
            return metadata
        return runtime_prompt_manifest

    legacy_metadata = {
        key: continuation_source[key]
        for key in ["previous_prompt", "topic", "instructions", "document_plan", "runtime_template", "context"]
        if key in continuation_source
    }
    return legacy_metadata or None


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
