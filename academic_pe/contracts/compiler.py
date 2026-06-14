from __future__ import annotations

import re
from typing import Any

from academic_pe.contracts.models import AgentContract, ArtifactContract
from academic_pe.contracts.validator import validate_agent_contract, validate_contract
from academic_pe.manifests.models import ArtifactManifest


_AGENT_ADAPTER_POLICIES: dict[str, dict[str, list[str]]] = {
    "prompt_enhancer": {
        "responsibilities": ["clarify_brief", "reduce_ambiguity", "preserve_artifact_intent"],
        "checks": ["candidate_contract_fit", "user_detail_retention", "scope_control"],
        "forbid": ["artifact_change", "scope_expansion", "academic_drift", "bureaucracy", "ai_markers"],
    },
    "planner": {
        "responsibilities": ["select_artifact_native_structure", "preserve_continuation_structure", "plan_deliverables"],
        "checks": ["structure_fit", "mode_compatibility", "negative_constraints"],
        "forbid": ["generic_research_paper_sections", "unrequested_academic_apparatus", "forced_visualization"],
    },
    "writer": {
        "responsibilities": ["produce_final_content", "preserve_voice_genre_audience", "satisfy_user_constraints"],
        "checks": ["contract_compliance", "style_fit", "ai_marker_absence"],
        "forbid": ["contract_analysis_output", "meta_text", "placeholder_text", "academic_drift"],
    },
    "reviewer": {
        "responsibilities": ["quality_gate", "detect_drift", "check_missing_constraints"],
        "checks": ["genre_drift", "style_drift", "audience_drift", "structure_drift", "ai_markers"],
        "forbid": ["rubric_drift", "incompatible_academicization", "generic_ai_filler"],
    },
    "researcher": {
        "responsibilities": ["source_only_when_required", "summarize_relevant_findings", "avoid_evidence_overreach"],
        "checks": ["source_relevance", "citation_quality", "source_need"],
        "forbid": ["unrequested_citations", "source_hunting_for_creative_artifacts", "unsupported_claims"],
    },
    "exporter": {
        "responsibilities": ["format_artifact", "preserve_output_constraints", "prepare_delivery"],
        "checks": ["format_compatibility", "heading_policy", "citation_section_policy"],
        "forbid": ["unrequested_title_page", "unrequested_citation_section", "rubric_text"],
    },
    "renderer": {
        "responsibilities": ["format_artifact", "preserve_output_constraints", "prepare_delivery"],
        "checks": ["format_compatibility", "heading_policy", "citation_section_policy"],
        "forbid": ["unrequested_title_page", "unrequested_citation_section", "rubric_text"],
    },
}

_FALLBACK_AGENT_POLICY = {
    "responsibilities": ["perform_role", "preserve_artifact_intent"],
    "checks": ["contract_compliance", "negative_constraints"],
    "forbid": ["artifact_change", "scope_expansion", "ai_markers"],
}


def compile_artifact_contract(
    manifest: ArtifactManifest,
    *,
    language: str = "auto",
    mode: str = "new",
    execution_mode: str = "standard",
    extra_requirements: dict[str, Any] | None = None,
) -> ArtifactContract:
    forbid = list(dict.fromkeys(manifest.forbid))
    requirements = dict(manifest.requirements)
    content_boundaries = dict(manifest.content_boundaries)
    visualization_required = bool(requirements.get("visualization_required", False))
    clauses = [_mode_clause(execution_mode)]

    overlay = manifest.modes.get(execution_mode)
    if overlay is not None:
        forbid = list(dict.fromkeys([*forbid, *overlay.add_forbid]))
        requirements.update(overlay.add_requirements)
        if overlay.visualization_policy == "required":
            visualization_required = True
        elif overlay.visualization_policy in {"forbidden", "compatible_only"}:
            visualization_required = False

    if extra_requirements:
        requirements.update(extra_requirements)
        visualization_required = bool(requirements.get("visualization_required", visualization_required))

    contract = ArtifactContract(
        manifest_id=manifest.id,
        manifest_version=manifest.version,
        artifact=manifest.artifact_type,
        language=language,
        style=manifest.style,
        audience=manifest.audience,
        mode=mode,
        execution_mode=execution_mode,
        clauses=clauses,
        structure=manifest.structure,
        forbid=forbid,
        requirements=requirements,
        content_boundaries=content_boundaries,
        visualization_required=visualization_required,
    )
    return validate_contract(contract)


def compile_agent_contract(
    artifact_contract: ArtifactContract,
    agent_name: str,
) -> AgentContract:
    agent = _normalize_agent_name(agent_name)
    policy = _AGENT_ADAPTER_POLICIES.get(agent, _FALLBACK_AGENT_POLICY)
    contract = AgentContract(
        agent=agent,
        artifact_contract=validate_contract(artifact_contract),
        responsibilities=_dedupe(policy["responsibilities"]),
        checks=_dedupe(policy["checks"]),
        forbid=_dedupe(policy["forbid"]),
    )
    return validate_agent_contract(contract)


def _mode_clause(execution_mode: str) -> str:
    normalized = execution_mode.strip().lower().replace("-", "_")
    if normalized.endswith("_mode"):
        return normalized
    return f"{normalized}_mode"


def _normalize_agent_name(agent_name: str) -> str:
    normalized = agent_name.strip().lower().replace("-", "_").replace(" ", "_")
    normalized = re.sub(r"[^a-z0-9_]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or "agent"


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
