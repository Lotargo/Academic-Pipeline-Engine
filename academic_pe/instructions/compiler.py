from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from academic_pe.contracts.models import ArtifactContract
from academic_pe.core.config import SectionPrompt
from academic_pe.core.document_assembly import CoverageMatrix
from academic_pe.core.document_ledger import DocumentLedger
from academic_pe.core.calculation_audit import CalculationLedger
from academic_pe.instructions.models import (
    CompiledInstructionBundle,
    Constraint,
    ContentReference,
    GatePlan,
    InstructionRole,
    OutputProtocol,
)
from academic_pe.instructions.section_brief import compile_section_brief


_OBJECTIVES = {
    InstructionRole.PLANNER: "Build the minimal sufficient document structure and assign content ownership.",
    InstructionRole.RESEARCHER: "Collect traceable evidence for the stated evidence needs.",
    InstructionRole.WRITER: "Draft the assigned section from its bounded brief and approved inputs.",
    InstructionRole.EVIDENCE_REVIEWER: "Find unsupported claims, source defects, and calculation defects.",
    InstructionRole.EDITORIAL_REVIEWER: "Find local clarity, coherence, repetition, and audience-fit issues.",
    InstructionRole.EXPORTER: "Render the approved document without changing its meaning.",
}

_PROTOCOLS = {
    InstructionRole.PLANNER: OutputProtocol(format="json", schema_id="document-plan-v1"),
    InstructionRole.RESEARCHER: OutputProtocol(format="json", schema_id="source-cards-v1"),
    InstructionRole.WRITER: OutputProtocol(format="text"),
    InstructionRole.EVIDENCE_REVIEWER: OutputProtocol(format="json", schema_id="review-issues-v1"),
    InstructionRole.EDITORIAL_REVIEWER: OutputProtocol(format="json", schema_id="review-issues-v1"),
    InstructionRole.EXPORTER: OutputProtocol(format="artifact"),
}


class InstructionCompiler:
    """Compile small, role-scoped instruction bundles from typed pipeline state."""

    def compile(
        self,
        role: InstructionRole | str,
        *,
        artifact_contract: ArtifactContract | None = None,
        section: SectionPrompt | None = None,
        coverage: Mapping[str, Any] | CoverageMatrix | None = None,
        section_names: Sequence[str] | None = None,
        content_inputs: Sequence[ContentReference | Mapping[str, Any]] = (),
        selected_skill_guidance: Sequence[str] = (),
        document_ledger: DocumentLedger | None = None,
        calculation_ledger: CalculationLedger | None = None,
    ) -> CompiledInstructionBundle:
        active_role = InstructionRole(role)
        if active_role is InstructionRole.WRITER and section is None:
            raise ValueError("writer instruction bundle requires a section")

        constraints = self._contract_constraints(active_role, artifact_contract)
        brief = None
        if active_role is InstructionRole.WRITER and section is not None:
            section_claims = [claim for claim in (document_ledger.claims if document_ledger else []) if claim.section_owner == section.name]
            source_ids = [source_id for claim in section_claims for source_id in claim.source_ids]
            calculation_ids = [
                entry.calculation_id
                for entry in (calculation_ledger.entries if calculation_ledger else [])
                if entry.section_owner == section.name
            ]
            brief = compile_section_brief(
                section,
                coverage=coverage,
                section_names=section_names,
                required_inputs=[*[claim.claim_id for claim in section_claims], *source_ids, *calculation_ids],
                allowed_sources=source_ids,
                calculations=calculation_ids,
            )

        return CompiledInstructionBundle(
            role=active_role,
            objective=_OBJECTIVES[active_role],
            hard_constraints=constraints,
            content_inputs=[ContentReference.model_validate(item) for item in content_inputs],
            section_brief=brief,
            selected_skill_guidance=list(dict.fromkeys(selected_skill_guidance)),
            output_protocol=_PROTOCOLS[active_role],
        )

    def gate_plan(self, artifact_contract: ArtifactContract | None = None) -> GatePlan:
        gates = ["prompt_leakage", "protocol_markers", "unicode_integrity"]
        if artifact_contract and artifact_contract.visualization_required:
            gates.append("visualization_presence")
        return GatePlan(gate_ids=gates)

    @staticmethod
    def _contract_constraints(
        role: InstructionRole,
        contract: ArtifactContract | None,
    ) -> list[Constraint]:
        if contract is None:
            return []
        values: list[tuple[str, str]] = []
        # Content and style constraints are useful to authoring roles. Export-only
        # mechanics deliberately never enter Writer bundles.
        if role in {InstructionRole.PLANNER, InstructionRole.WRITER, InstructionRole.EDITORIAL_REVIEWER}:
            values.extend(("style", value) for value in contract.style)
            values.extend(("clause", value) for value in contract.clauses)
        if role in {InstructionRole.PLANNER, InstructionRole.WRITER, InstructionRole.RESEARCHER, InstructionRole.EVIDENCE_REVIEWER}:
            values.extend(("forbid", value) for value in contract.forbid)
        if role is InstructionRole.EXPORTER:
            values.extend(("structure", value) for value in contract.structure)
        return [
            Constraint(id=f"artifact.{kind}.{index}", text=text, source="artifact_contract")
            for index, (kind, text) in enumerate(values, start=1)
            if str(text).strip()
        ]
