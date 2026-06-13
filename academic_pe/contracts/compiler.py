from __future__ import annotations

from typing import Any

from academic_pe.contracts.models import ArtifactContract
from academic_pe.manifests.models import ArtifactManifest


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
    visualization_required = bool(requirements.get("visualization_required", False))

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

    return ArtifactContract(
        manifest_id=manifest.id,
        manifest_version=manifest.version,
        artifact=manifest.artifact_type,
        language=language,
        style=manifest.style,
        audience=manifest.audience,
        mode=mode,
        execution_mode=execution_mode,
        structure=manifest.structure,
        forbid=forbid,
        requirements=requirements,
        visualization_required=visualization_required,
    )
