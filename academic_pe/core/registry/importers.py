import os
import json
import re
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from academic_pe.core.registry.models import (
    Run, RunAgent, Artifact, RuntimeSnapshot,
    Section, Source, Evaluation, Event
)
from academic_pe.core.registry.store import RegistryStore
from academic_pe.core.registry.checksums import get_file_metadata

logger = logging.getLogger(__name__)

RUN_ID_PATTERN = re.compile(r"^run_\d{8}_\d{6}$")

def is_valid_run_id(run_id: Any) -> bool:
    return isinstance(run_id, str) and bool(RUN_ID_PATTERN.match(run_id))

def run_id_from_filename(filename: Any) -> Optional[str]:
    if not isinstance(filename, str):
        return None
    normalized = filename.replace("\\", "/")
    first_part = normalized.split("/", 1)[0]
    return first_part if is_valid_run_id(first_part) else None

def run_id_from_metadata_id(metadata_id: str) -> Optional[str]:
    stem = metadata_id.split(".", 1)[0]
    return stem if is_valid_run_id(stem) else None

def resolve_run_id(metadata_id: str, data: dict) -> Optional[str]:
    candidates = [
        data.get("run_id"),
        run_id_from_filename(data.get("docx_filename")),
        run_id_from_filename(data.get("pdf_filename")),
        run_id_from_metadata_id(metadata_id),
    ]
    return next((candidate for candidate in candidates if is_valid_run_id(candidate)), None)

def safe_relative_path(path: str) -> str:
    """Calculates relative path, falling back to absolute if on different drives on Windows."""
    try:
        return os.path.relpath(path, start=os.getcwd()).replace("\\", "/")
    except ValueError:
        return os.path.abspath(path).replace("\\", "/")

def import_metadata_json(
    store: RegistryStore,
    metadata_path: str,
    output_dir: str = "exports"
) -> Optional[str]:
    """
    Imports a single legacy metadata.json file into the SQLite registry.
    Returns the run_id if imported successfully, else None.
    """
    if not os.path.exists(metadata_path):
        logger.warning("Metadata file not found: %s", metadata_path)
        return None
        
    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error("Failed to parse metadata JSON at %s: %s", metadata_path, e)
        return None

    filename = os.path.basename(metadata_path)
    run_id = resolve_run_id(filename, data)
    if not run_id:
        logger.warning("Could not resolve a valid run_id for metadata file %s", filename)
        return None
        

    # Determine status
    status_raw = data.get("status", "COMPLETED")
    status = "succeeded" if status_raw == "COMPLETED" else status_raw.lower()
    if status not in ("created", "running", "succeeded", "failed", "cancelled"):
        status = "succeeded"

    # Pipeline mode
    pipeline_mode = "standard"
    if data.get("continuation_intent") or data.get("continuation_source"):
        pipeline_mode = "continuation"
    elif data.get("pipeline_mode"):
        pipeline_mode = data.get("pipeline_mode")

    # Created at / timestamp
    created_at = data.get("timestamp")
    if not created_at:
        # Fallback to parsed run_id timestamp or file modification time
        match = re.match(r"run_(\d{8})_(\d{6})", run_id)
        if match:
            date_str, time_str = match.groups()
            try:
                created_at = datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S").isoformat()
            except ValueError:
                created_at = datetime.fromtimestamp(os.path.getctime(metadata_path)).isoformat()
        else:
            created_at = datetime.fromtimestamp(os.path.getctime(metadata_path)).isoformat()

    # Collect fields that the history API needs to reconstruct a legacy-compatible item.
    metadata_fields = {
        "author": data.get("author"),
        "previous_prompt": data.get("previous_prompt"),
        "academic_mode": data.get("academic_mode", False),
        "archived": data.get("archived", False),
        "archived_at": data.get("archived_at"),
        "context": data.get("context", {}),
        "document_plan": data.get("document_plan"),
        "self_critique_summary": data.get("self_critique_summary"),
        "reviewer_feedback": data.get("reviewer_feedback"),
        "original_context": data.get("original_context"),
        "logs": data.get("logs", []),
        "export_report": data.get("export_report"),
        "template_mode": data.get("template_mode"),
        "template_id": data.get("template_id"),
        "resolved_manifest": data.get("resolved_manifest"),
        "resolved_contract": data.get("resolved_contract"),
        "contract_sexpr": data.get("contract_sexpr"),
        "manifest_selection": data.get("manifest_selection"),
        "decision_summary": data.get("decision_summary"),
        "artifact_override": data.get("artifact_override"),
        "continuation_intent": data.get("continuation_intent"),
        "document_state": data.get("document_state"),
        "edit_plan": data.get("edit_plan"),
        "merge_patch": data.get("merge_patch"),
        "legacy_metadata_file": filename
    }
    
    # Instantiate Run
    run = Run(
        run_id=run_id,
        kind="generation",
        status=status,
        topic=data.get("topic", "Unknown"),
        instructions_preview=data.get("instructions"),
        pipeline_mode=pipeline_mode,
        web_search_enabled=bool(data.get("web_search_enabled", False)),
        created_at=created_at,
        started_at=created_at,
        finished_at=created_at if status in ("succeeded", "failed", "cancelled") else None,
        output_dir=os.path.join(output_dir, run_id),
        metadata_json=json.dumps(metadata_fields, ensure_ascii=False)
    )
    
    # Check if run already exists in DB
    existing_run = store.get_run(run_id)
    if existing_run:
        logger.info("Run %s already exists in registry, updating run metadata.", run_id)
        store.update_run(run)
        # Clean up existing relations that this import will overwrite
        store.delete_run_artifacts(run_id)
        store.delete_run_snapshots(run_id)
        store.delete_run_sources(run_id)
    else:
        # Create the run in the store
        store.create_run(run)
    
    # Import runtime snapshots
    for snapshot_key, snapshot_type in [("runtime_template", "runtime_template"), ("runtime_prompt_manifest", "runtime_prompt_manifest")]:
        snapshot_data = data.get(snapshot_key)
        if snapshot_data:
            snapshot = RuntimeSnapshot(
                run_id=run_id,
                snapshot_type=snapshot_type,
                version=None,
                fingerprint=None,
                metadata_json=json.dumps(snapshot_data, ensure_ascii=False)
            )
            store.add_runtime_snapshot(snapshot)

    # Import artifacts
    # 1. DOCX output
    docx_filename = data.get("docx_filename")
    if docx_filename:
        # Check output_dir or absolute path
        possible_paths = [
            os.path.join(output_dir, docx_filename),
            os.path.join(output_dir, run_id, docx_filename),
            docx_filename
        ]
        actual_path = ""
        for p in possible_paths:
            if os.path.exists(p) and os.path.isfile(p):
                actual_path = p
                break
                
        if not actual_path:
            actual_path = os.path.join(output_dir, docx_filename)
            
        size, sha = get_file_metadata(actual_path)
        
        artifact = Artifact(
            run_id=run_id,
            artifact_type="docx",
            path=os.path.abspath(actual_path),
            relative_path=safe_relative_path(actual_path),
            filename=os.path.basename(docx_filename),
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            size_bytes=size if size > 0 else None,
            sha256=sha if sha else None,
            created_at=created_at,
            is_diagnostic=False,
            metadata_json=None
        )
        store.add_artifact(artifact)

    # 2. PDF output
    pdf_filename = data.get("pdf_filename")
    if pdf_filename:
        possible_paths = [
            os.path.join(output_dir, pdf_filename),
            os.path.join(output_dir, run_id, pdf_filename),
            pdf_filename
        ]
        actual_path = ""
        for p in possible_paths:
            if os.path.exists(p) and os.path.isfile(p):
                actual_path = p
                break
                
        if not actual_path:
            actual_path = os.path.join(output_dir, pdf_filename)
            
        size, sha = get_file_metadata(actual_path)
        
        artifact = Artifact(
            run_id=run_id,
            artifact_type="pdf",
            path=os.path.abspath(actual_path),
            relative_path=safe_relative_path(actual_path),
            filename=os.path.basename(pdf_filename),
            mime_type="application/pdf",
            size_bytes=size if size > 0 else None,
            sha256=sha if sha else None,
            created_at=created_at,
            is_diagnostic=False,
            metadata_json=None
        )
        store.add_artifact(artifact)

    # 3. Import the metadata JSON file itself as a diagnostic artifact
    size, sha = get_file_metadata(metadata_path)
    meta_artifact = Artifact(
        run_id=run_id,
        artifact_type="json",
        path=os.path.abspath(metadata_path),
        relative_path=safe_relative_path(metadata_path),
        filename=filename,
        mime_type="application/json",
        size_bytes=size if size > 0 else None,
        sha256=sha if sha else None,
        created_at=created_at,
        is_diagnostic=True,
        metadata_json=None
    )
    store.add_artifact(meta_artifact)

    # Import continuation source if present
    continuation_source = data.get("continuation_source")
    if continuation_source and isinstance(continuation_source, dict):
        source = Source(
            run_id=run_id,
            source_type="continuation",
            title=continuation_source.get("topic") or "Continuation Source",
            url=None,
            path=continuation_source.get("docx_filename"),
            sha256=None,
            used_by="planner",
            metadata_json=json.dumps(continuation_source, ensure_ascii=False)
        )
        store.add_source(source)

    return run_id

def import_all_metadata_jsons(
    store: RegistryStore,
    metadata_dir: str = "exports/_metadata",
    output_dir: str = "exports"
) -> List[str]:
    """
    Scans a directory and imports all *.metadata.json files.
    Returns a list of successfully imported run_ids.
    """
    imported_run_ids = []
    if not os.path.exists(metadata_dir) or not os.path.isdir(metadata_dir):
        logger.warning("Metadata directory does not exist: %s", metadata_dir)
        return imported_run_ids
        
    for name in os.listdir(metadata_dir):
        if name.endswith(".metadata.json"):
            path = os.path.join(metadata_dir, name)
            run_id = import_metadata_json(store, path, output_dir=output_dir)
            if run_id:
                imported_run_ids.append(run_id)
                
    return imported_run_ids
