import warnings
warnings.filterwarnings("ignore", category=PendingDeprecationWarning)

import os
import json
import yaml
import logging
import threading
import asyncio
import time
import re
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse

from academic_pe.api_models import BulkHistoryPayload, ConfigUpdateRequest, ExportRequest, RevisionCreateRequest, RunRequest, SecretUpdatePayload, PromptEnhanceRequest, PromptEnhanceResponse
from academic_pe.core.config import TemplateMode, load_config, AppConfig
from academic_pe.core.continuation import is_terminal_section_name
from academic_pe.core.document_structure import is_renderable_section
from academic_pe.core.orchestrator import create_orchestrator_from_config, PipelineState, PipelineCancelled
from academic_pe.core.template_library import TemplateLibrary
from academic_pe.tools.export_qa import export_docx_with_qa, export_pdf_with_qa
from academic_pe.tools.libreoffice import discover_soffice
from academic_pe.observability import CorrelationIdMiddleware, ObservabilityConfig, TelemetryStore

from academic_pe.core.registry import SQLiteRegistryStore, NoopRegistryStore
# Initialize registry store
try:
    registry_store = SQLiteRegistryStore("exports/_metadata/academic_pe_registry.sqlite3")
except Exception as e:
    logging.getLogger(__name__).warning("Failed to initialize SQLite Registry, falling back to Noop: %s", e)
    registry_store = NoopRegistryStore()

_background_tasks = set()

REFERENCE_ATTACHMENT_EXTENSIONS = {".pdf", ".docx", ".md", ".txt", ".csv", ".xlsx", ".pptx"}
CONTINUATION_ATTACHMENT_EXTENSIONS = {".pdf", ".docx", ".md", ".txt"}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Clean up empty run directories on startup
    cleanup_empty_run_directories()

    # Import legacy metadata JSONs on startup
    try:
        from academic_pe.core.registry import import_all_metadata_jsons
        import_all_metadata_jsons(registry_store)
        logging.getLogger(__name__).info("Successfully imported legacy metadata into SQLite Registry.")
    except Exception as e:
        logging.getLogger(__name__).warning("Failed to import legacy metadata into SQLite Registry: %s", e)
    
    # Start dynamic examples generator loop
    from academic_pe.core.dynamic_examples import dynamic_examples_loop
    task = asyncio.create_task(dynamic_examples_loop())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    
    yield
    
    # Cancel the task on shutdown
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

# Create FastAPI app
app = FastAPI(title="Academic PE API Server", version="0.1.0", lifespan=lifespan)
try:
    _observability_config = ObservabilityConfig.from_yaml()
except Exception as exc:
    logging.getLogger(__name__).warning("Invalid observability configuration; using safe defaults: %s", exc)
    _observability_config = ObservabilityConfig()
telemetry_store = TelemetryStore(
    max_events=_observability_config.retention.telemetry_max_events,
    retention_seconds=_observability_config.retention.telemetry_event_seconds,
)
app.add_middleware(CorrelationIdMiddleware, telemetry=telemetry_store)

# Multi-user auth is enabled only for the service deployment. The legacy local-first
# server remains usable without PostgreSQL or a JWT secret.
if os.getenv("APE_DATABASE_SYNC_URL"):
    from academic_pe.auth import AuthSettings, create_auth_router
    from academic_pe.jobs import create_jobs_router
    from academic_pe.persistence.config import DatabaseSettings, create_worker_engine, create_worker_session_factory

    _auth_secret = os.getenv("APE_AUTH_JWT_SECRET")
    if not _auth_secret:
        raise RuntimeError("APE_AUTH_JWT_SECRET is required when service auth is enabled")
    _database_settings = DatabaseSettings.from_env()
    _auth_engine = create_worker_engine(_database_settings)
    _session_factory = create_worker_session_factory(_auth_engine)
    _auth_router = create_auth_router(_session_factory, AuthSettings(_auth_secret))
    app.include_router(_auth_router)
    app.include_router(create_jobs_router(_session_factory, _auth_router.principal_dependency))

# CORS middleware for Next.js on port 3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-ID"],
)


@app.get("/healthz", include_in_schema=False)
def healthz(request: Request):
    """Liveness only: never disclose provider, secret, or database settings."""

    return {
        "status": "ok",
        "correlation_id": getattr(request.state, "correlation_id", None),
    }


@app.get("/readyz", include_in_schema=False)
def readyz(request: Request):
    """Safe readiness for an API process; dependency diagnostics stay internal."""

    return {
        "status": "ready",
        "checks": {"api": "ok"},
        "correlation_id": getattr(request.state, "correlation_id", None),
    }


@app.get("/metrics", include_in_schema=False)
def metrics():
    return PlainTextResponse(telemetry_store.prometheus_metrics(), media_type="text/plain; version=0.0.4")

# Mount static files for exports directory to serve generated charts and other files
from fastapi.staticfiles import StaticFiles
os.makedirs("exports", exist_ok=True)
app.mount("/api/exports", StaticFiles(directory="exports"), name="exports")


# Global status tracking object
current_run: Dict[str, Any] = {
    "status": "IDLE",  # IDLE, RUNNING, COMPLETED, FAILED
    "state": "INIT",
    "logs": [],
    "context": {},
    "original_context": {},
    "reviewer_feedback": [],
    "docx_filename": None,
    "pdf_filename": None,
    "export_report": None,
    "error": None,
    "topic": "",
    "instructions": None,
    "timestamp": None,
    "author": None,
    "active_section": None,
    "template_mode": None,
    "template_id": None,
    "runtime_template": None,
    "runtime_prompt_manifest": None,
    "academic_mode": False,
    "run_id": None,
    "document_plan": None,
    "continuation_source": None,
    "resolved_manifest": None,
    "resolved_contract": None,
    "contract_sexpr": None,
    "manifest_selection": None,
    "decision_summary": None,
    "artifact_override": None,
    "continuation_intent": None,
    "document_state": None,
    "edit_plan": None,
    "merge_patch": None,
    "revisions": [],
    "document_ledger": None,
    "calculation_ledger": None,
}


def _exportable_context(context: Dict[str, str]) -> Dict[str, str]:
    return {key: value for key, value in context.items() if key != "document_plan"}


def _terminal_section_names_from_runtime_template_data(rt_data: Optional[dict]) -> List[str]:
    if not isinstance(rt_data, dict):
        return []

    terminal_names: List[str] = []
    metadata = rt_data.get("metadata")
    document_state = metadata.get("document_state") if isinstance(metadata, dict) else None
    if isinstance(document_state, dict):
        terminal_names.extend(
            str(section)
            for section in document_state.get("terminal_sections", [])
            if str(section)
        )

    sections = rt_data.get("sections")
    if isinstance(sections, list):
        for section in sections:
            if not isinstance(section, dict):
                continue
            name = str(section.get("name") or "")
            title = str(section.get("title") or section.get("topic") or "")
            role = str(section.get("semantic_role") or "")
            if (
                role in {"reference_section", "appendix", "glossary"}
                or is_terminal_section_name(name)
                or is_terminal_section_name(title)
            ):
                terminal_names.append(name)

    seen = set()
    result: List[str] = []
    for name in terminal_names:
        if not name or name in seen:
            continue
        seen.add(name)
        result.append(name)
    return result


def _move_terminal_export_sections_to_end(
    context: Dict[str, str],
    terminal_sections: List[str],
) -> Dict[str, str]:
    terminal_set = {section for section in terminal_sections if section in context}
    if not terminal_set:
        return context
    result = {
        key: value
        for key, value in context.items()
        if key not in terminal_set
    }
    for key, value in context.items():
        if key in terminal_set:
            result[key] = value
    return result


def _align_config_sections_to_export_context(config: AppConfig, export_context: Dict[str, str]) -> AppConfig:
    order_index = {name: index for index, name in enumerate(export_context.keys())}
    config.pipeline.sections = sorted(
        config.pipeline.sections,
        key=lambda section: order_index.get(section.name, len(order_index)),
    )
    return config


# Thread lock for safety
run_lock = threading.Lock()

# Current orchestrator instance for cancellation
_current_orchestrator = None
_orchestrator_lock = threading.Lock()


def _delete_run_directory(run_id: str) -> None:
    import re
    import shutil
    if not run_id:
        return
    # Validate run_id to prevent directory traversal or accidental deletion of important directories
    if not re.match(r"^run_\d{8}_\d{6}$", run_id):
        return
    run_dir = os.path.join("exports", run_id)
    if os.path.exists(run_dir) and os.path.isdir(run_dir):
        try:
            shutil.rmtree(run_dir)
            logging.getLogger(__name__).info("Deleted run directory: %s", run_dir)
        except Exception as e:
            logging.getLogger(__name__).warning("Failed to delete run directory %s: %s", run_dir, e)


def _cleanup_run_directory(run_id: str, success: bool) -> None:
    import re
    import shutil
    if not run_id or not re.match(r"^run_\d{8}_\d{6}$", run_id):
        return
    run_dir = os.path.join("exports", run_id)
    if os.path.exists(run_dir) and os.path.isdir(run_dir):
        try:
            if not success:
                shutil.rmtree(run_dir)
                logging.getLogger(__name__).info("Cleaned up failed/cancelled run directory: %s", run_dir)
            else:
                # If successful, delete only if it is empty
                if not os.listdir(run_dir):
                    os.rmdir(run_dir)
                    logging.getLogger(__name__).info("Cleaned up empty successful run directory: %s", run_dir)
        except Exception as e:
            logging.getLogger(__name__).warning("Failed to clean up run directory %s: %s", run_dir, e)


def cleanup_empty_run_directories() -> None:
    import re
    exports_dir = "exports"
    if not os.path.exists(exports_dir) or not os.path.isdir(exports_dir):
        return
    try:
        cleaned_count = 0
        for name in os.listdir(exports_dir):
            path = os.path.join(exports_dir, name)
            if os.path.isdir(path) and re.match(r"^run_\d{8}_\d{6}$", name):
                if not os.listdir(path):
                    os.rmdir(path)
                    cleaned_count += 1
        if cleaned_count > 0:
            logging.getLogger(__name__).info("Cleaned up %d empty run directories on startup.", cleaned_count)
    except Exception as e:
        logging.getLogger(__name__).warning("Failed to run startup cleanup of run directories: %s", e)


def _pipeline_output_dir() -> str:
    try:
        config = load_config("config/agents.yaml")
        return config.pipeline.output_dir
    except Exception:
        return "exports"


def _metadata_dir(output_dir: str) -> str:
    return os.path.join(output_dir, "_metadata")


def _history_metadata_dir() -> str:
    return os.path.join("exports", "_metadata")


def _build_previous_prompt(topic: Optional[str], instructions: Optional[str]) -> Optional[str]:
    parts = []
    if topic:
        parts.append(f"Topic: {topic}")
    if instructions:
        parts.append(f"Instructions: {instructions}")
    return "\n".join(parts) if parts else None


RUN_ID_PATTERN = re.compile(r"^run_\d{8}_\d{6}$")


def _is_valid_run_id(run_id: object) -> bool:
    return isinstance(run_id, str) and bool(RUN_ID_PATTERN.match(run_id))


def _run_id_from_export_filename(filename: object) -> Optional[str]:
    if not isinstance(filename, str):
        return None
    normalized = filename.replace("\\", "/")
    first_part = normalized.split("/", 1)[0]
    return first_part if _is_valid_run_id(first_part) else None


def _run_id_from_metadata_id(metadata_id: str) -> Optional[str]:
    stem = metadata_id.split(".", 1)[0]
    return stem if _is_valid_run_id(stem) else None


def _resolve_history_run_id(metadata_id: str, data: dict) -> Optional[str]:
    candidates = [
        data.get("run_id"),
        _run_id_from_export_filename(data.get("docx_filename")),
        _run_id_from_export_filename(data.get("pdf_filename")),
        _run_id_from_metadata_id(metadata_id),
    ]
    return next((candidate for candidate in candidates if _is_valid_run_id(candidate)), None)


def _safe_metadata_path(metadata_id: str) -> str:
    if not metadata_id or metadata_id != os.path.basename(metadata_id):
        raise HTTPException(status_code=400, detail="Invalid history metadata id")
    if not metadata_id.endswith(".metadata.json"):
        raise HTTPException(status_code=400, detail="Invalid history metadata id")

    metadata_dir = os.path.abspath(_history_metadata_dir())
    metadata_path = os.path.abspath(os.path.join(metadata_dir, metadata_id))
    if not metadata_path.startswith(metadata_dir + os.sep):
        raise HTTPException(status_code=403, detail="Access denied")
    if not os.path.exists(metadata_path):
        raise HTTPException(status_code=404, detail="History item not found")
    return metadata_path


def _load_history_metadata(metadata_id: str) -> tuple[str, dict]:
    metadata_path = _safe_metadata_path(metadata_id)
    try:
        with open(metadata_path, "r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="History metadata is not valid JSON")
    return metadata_path, data


def _write_history_metadata(metadata_path: str, data: dict) -> None:
    data["updated_at"] = datetime.now().isoformat(timespec="seconds")
    with open(metadata_path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
    try:
        from academic_pe.core.registry import import_metadata_json
        import_metadata_json(registry_store, metadata_path)
    except Exception as ree:
        logging.getLogger(__name__).warning("Failed to sync written metadata to SQLite registry: %s", ree)


def _metadata_for_run_id(run_id: str) -> tuple[str, dict]:
    """Resolve the most recently updated local history record for a run."""
    if not _is_valid_run_id(run_id):
        raise HTTPException(status_code=400, detail="Invalid run_id")
    metadata_dir = _history_metadata_dir()
    candidates: list[tuple[float, str, dict]] = []
    if os.path.isdir(metadata_dir):
        for name in os.listdir(metadata_dir):
            if not name.endswith(".metadata.json"):
                continue
            path = os.path.join(metadata_dir, name)
            try:
                with open(path, "r", encoding="utf-8") as file:
                    data = json.load(file)
                if _resolve_history_run_id(name, data) == run_id:
                    candidates.append((os.path.getmtime(path), path, data))
            except (OSError, json.JSONDecodeError):
                continue
    if not candidates:
        raise HTTPException(status_code=404, detail="Run history item not found")
    _, path, data = max(candidates, key=lambda item: item[0])
    return path, data


def _history_item_from_metadata(metadata_id: str, data: dict) -> dict:
    run_id = _resolve_history_run_id(metadata_id, data)
    output_dir = _pipeline_output_dir()

    def file_size(filename: Optional[str]) -> Optional[int]:
        if not filename:
            return None
        try:
            candidate = os.path.abspath(os.path.join(output_dir, filename))
            root = os.path.abspath(output_dir)
            return os.path.getsize(candidate) if candidate.startswith(root + os.sep) and os.path.isfile(candidate) else None
        except OSError:
            return None

    from academic_pe.core.revision import revision_history
    revisions = [item.model_dump(mode="json") for item in revision_history(data)]
    return {
        "id": metadata_id,
        "run_id": run_id,
        "filename": data.get("docx_filename"),
        "pdf_filename": data.get("pdf_filename"),
        "artifact_sizes": {
            "docx": file_size(data.get("docx_filename")),
            "pdf": file_size(data.get("pdf_filename")),
        },
        "topic": data.get("topic", "Unknown"),
        "instructions": data.get("instructions"),
        "previous_prompt": data.get("previous_prompt"),
        "timestamp": data.get("timestamp", ""),
        "author": data.get("author"),
        "status": data.get("status", "COMPLETED"),
        "archived": bool(data.get("archived", False)),
        "archived_at": data.get("archived_at"),
        "context": data.get("context", {}),
        "document_plan": data.get("document_plan"),
        "original_context": data.get("original_context", {}),
        "academic_mode": data.get("academic_mode", False),
        "logs": data.get("logs", []),
        "reviewer_feedback": data.get("reviewer_feedback", []),
        "export_report": data.get("export_report"),
        "template_mode": data.get("template_mode"),
        "template_id": data.get("template_id"),
        "runtime_template": data.get("runtime_template"),
        "runtime_prompt_manifest": data.get("runtime_prompt_manifest"),
        "resolved_manifest": data.get("resolved_manifest"),
        "resolved_contract": data.get("resolved_contract"),
        "contract_sexpr": data.get("contract_sexpr"),
        "manifest_selection": data.get("manifest_selection"),
        "decision_summary": data.get("decision_summary"),
        "continuation_source": data.get("continuation_source"),
        "artifact_override": data.get("artifact_override"),
        "continuation_intent": data.get("continuation_intent"),
        "document_state": data.get("document_state"),
        "edit_plan": data.get("edit_plan"),
        "merge_patch": data.get("merge_patch"),
        "revisions": revisions,
        "latest_revision": revisions[-1]["revision"] if revisions else 1,
    }


def _load_legacy_metadata_for_registry_item(metadata_id: Optional[str]) -> dict:
    if not metadata_id:
        return {}
    try:
        metadata_path = _safe_metadata_path(metadata_id)
        with open(metadata_path, "r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _hydrate_registry_metadata(meta: dict) -> dict:
    legacy_data = _load_legacy_metadata_for_registry_item(meta.get("legacy_metadata_file"))
    if not legacy_data:
        return meta
    merged = dict(legacy_data)
    overrides = {
        key: value
        for key, value in meta.items()
        if value is not None and not (key in {"context", "original_context"} and value == {})
    }
    merged.update(overrides)
    return merged


def _artifact_manifest_metadata(runtime_prompt_manifest: Optional[dict]) -> dict:
    if not isinstance(runtime_prompt_manifest, dict):
        return {}

    metadata = runtime_prompt_manifest.get("metadata")
    if not isinstance(metadata, dict):
        return {}

    keys = [
        "resolved_manifest",
        "resolved_contract",
        "contract_sexpr",
        "manifest_selection",
        "decision_summary",
    ]
    return {key: metadata[key] for key in keys if key in metadata}


def _with_artifact_manifest_metadata(metadata: dict) -> dict:
    runtime_prompt_manifest = metadata.get("runtime_prompt_manifest")
    artifact_metadata = _artifact_manifest_metadata(runtime_prompt_manifest)
    for key, value in artifact_metadata.items():
        metadata.setdefault(key, value)
    return metadata


def _editorial_runtime_metadata(runtime_prompt_manifest: Optional[dict]) -> dict:
    if not isinstance(runtime_prompt_manifest, dict):
        return {}
    metadata = runtime_prompt_manifest.get("metadata")
    if not isinstance(metadata, dict):
        return {}
    keys = ["continuation_intent", "document_state", "edit_plan", "merge_patch"]
    return {key: metadata[key] for key in keys if key in metadata}


def _delete_export_asset(docx_name: Optional[str]) -> None:
    if not docx_name:
        return

    output_dir = os.path.abspath(_pipeline_output_dir())
    file_path = os.path.abspath(os.path.join(output_dir, docx_name))
    if not file_path.startswith(output_dir + os.sep):
        raise HTTPException(status_code=403, detail="Export path is outside the output directory")
    if os.path.exists(file_path) and os.path.isfile(file_path):
        os.remove(file_path)


def _apply_continuation_structure(config: AppConfig, continuation_source: Optional[dict]) -> AppConfig:
    if not continuation_source:
        return config

    runtime_template_data = continuation_source.get("runtime_template")
    if isinstance(runtime_template_data, dict):
        try:
            from academic_pe.core.orchestrator import _apply_runtime_template
            from academic_pe.core.templates import RuntimeTemplate

            runtime_template = RuntimeTemplate(**runtime_template_data)
            resolved = _apply_runtime_template(config, runtime_template)
            resolved.pipeline.template_mode = TemplateMode.custom
            return resolved
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "Failed to reuse continuation runtime template: %s", exc
            )

    context = continuation_source.get("context")
    if isinstance(context, dict):
        from academic_pe.core.config import SectionPrompt

        sections = []
        for name, content in context.items():
            if name == "document_plan" or not content:
                continue
            sections.append(
                SectionPrompt(
                    name=name,
                    topic=name.replace("_", " ").replace("-", " ").title(),
                    instruction=(
                        "Continue from the previous work in the same genre, register, narrative voice, "
                        "style, audience level, and structure unless the new user request explicitly changes them."
                    ),
                )
            )
        if sections:
            config.pipeline.sections = sections
            config.pipeline.template_mode = TemplateMode.custom

    return config

# Custom logger handler
class StatusLogHandler(logging.Handler):
    def __init__(self, logs_list: List[str]):
        super().__init__()
        self.logs_list = logs_list
        self.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

    def emit(self, record):
        try:
            msg = self.format(record)
            self.logs_list.append(msg)
        except Exception:
            self.handleError(record)

# Initialize standard logging
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Routes
@app.get("/api/config")
def get_config():
    config_path = "config/agents.yaml"
    if not os.path.exists(config_path):
        raise HTTPException(status_code=404, detail="Config file not found")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read config: {str(e)}")


@app.get("/api/examples")
async def get_examples(client_time: Optional[float] = None):
    """
    Returns the list of research examples/templates.
    Optionally aligns generation timestamps and TTL to browser's client_time (millisecond epoch).
    """
    config = load_config("config/agents.yaml")
    lang = config.ui.language
    
    if not getattr(config, "dynamic_examples_enabled", True):
        from academic_pe.core.dynamic_examples import get_default_examples
        return {
            "examples": get_default_examples(lang),
            "last_generated": time.time() * 1000,
            "ttl": 0,
            "dynamic": False
        }
        
    from academic_pe.core.dynamic_examples import load_cached_examples, last_generated_at
    examples = await load_cached_examples(lang)
    
    now = time.time()
    interval_mins = getattr(config, "dynamic_examples_interval_mins", 15)
    interval_sec = max(interval_mins, 1) * 60
    
    elapsed = now - last_generated_at
    ttl = max(0.0, interval_sec - elapsed)
    
    last_generated_client_ms = last_generated_at * 1000
    if client_time is not None:
        client_time_sec = client_time / 1000.0
        drift = client_time_sec - now
        last_generated_client_ms = (last_generated_at + drift) * 1000
        
    return {
        "examples": examples,
        "last_generated": last_generated_client_ms,
        "ttl": int(ttl),
        "dynamic": True
    }


@app.post("/api/examples/refresh")
async def refresh_examples():
    """
    Manually triggers generation of new dynamic examples and returns them.
    """
    from academic_pe.core import dynamic_examples

    refreshed = True
    refresh_error = None
    try:
        await dynamic_examples.generate_new_examples()
    except Exception as e:
        refreshed = False
        refresh_error = str(e) or e.__class__.__name__
        logging.getLogger(__name__).warning(
            "Manual dynamic examples refresh failed; returning cached examples: %s",
            refresh_error,
        )

    try:
        config = load_config("config/agents.yaml")
        lang = config.ui.language
        interval_sec = max(getattr(config, "dynamic_examples_interval_mins", 15) * 60, 60)
    except Exception:
        lang = "ru"
        interval_sec = 15 * 60

    try:
        examples = await dynamic_examples.load_cached_examples(lang)
        response = {
            "examples": examples,
            "last_generated": dynamic_examples.last_generated_at * 1000,
            "ttl": interval_sec,
            "dynamic": True,
            "refreshed": refreshed,
        }
        if refresh_error:
            response["error"] = f"Failed to generate new examples: {refresh_error}"
        return response
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to load examples: {str(e)}")


def _build_prompt_enhancement_prompt(
    topic: str,
    instructions: Optional[str],
    lang: str,
    academic_mode: bool = False,
    artifact_override: Optional[str] = None,
) -> str:
    """Deprecated compatibility builder retained for API clients and stored tests."""
    from academic_pe.agent_adapters import build_prompt_enhancement_prompt

    return build_prompt_enhancement_prompt(
        topic=topic,
        instructions=instructions,
        language=lang,
        academic_mode=academic_mode,
        artifact_override=artifact_override,
    )


def _build_brief_normalization_prompt(
    topic: str,
    instructions: Optional[str],
    lang: str,
    academic_mode: bool = False,
    artifact_override: Optional[str] = None,
) -> str:
    from academic_pe.agent_adapters import build_brief_normalization_prompt

    return build_brief_normalization_prompt(
        topic=topic,
        instructions=instructions,
        language=lang,
        academic_mode=academic_mode,
        artifact_override=artifact_override,
    )


def _extract_prompt_enhancement_json(raw_response: str) -> dict:
    text = (raw_response or "").strip()
    if "```" in text:
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if match:
            text = match.group(1).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ValueError("No JSON object structure found in the agent response")
        data = json.loads(text[start:end + 1])

    if not isinstance(data, dict):
        raise ValueError("Parsed JSON is not an object")
    return data


def _normalize_prompt_enhancement_response(
    raw_response: str,
    *,
    fallback_topic: str,
    fallback_instructions: Optional[str],
) -> tuple[str, str, bool]:
    fallback_topic_text = fallback_topic.strip()
    fallback_instructions_text = (fallback_instructions or "").strip()
    try:
        data = _extract_prompt_enhancement_json(raw_response)
    except Exception:
        return fallback_topic_text, fallback_instructions_text, bool(fallback_topic_text or fallback_instructions_text)

    raw_topic = data.get("topic")
    raw_instructions = data.get("instructions")
    if not isinstance(raw_instructions, str):
        from academic_pe.instructions.brief import NormalizedBrief

        try:
            raw_instructions = NormalizedBrief.model_validate(data).legacy_instructions()
        except Exception:
            raw_instructions = None
    has_topic = isinstance(raw_topic, str) and bool(raw_topic.strip())
    has_instructions = isinstance(raw_instructions, str) and bool(raw_instructions.strip())
    topic = raw_topic.strip() if has_topic else fallback_topic_text
    instructions = (
        raw_instructions.strip()
        if has_instructions
        else fallback_instructions_text
    )
    fallback_used = (
        (not has_topic and bool(fallback_topic_text))
        or (not has_instructions and bool(fallback_instructions_text))
    )
    return topic, instructions, fallback_used


def _resolve_prompt_enhancement_metadata(
    *,
    topic: str,
    instructions: str,
    academic_mode: bool,
    language: str,
    artifact_override: Optional[str],
) -> dict:
    from academic_pe.manifests import ArtifactManifestResolver

    try:
        resolver = ArtifactManifestResolver()
        resolved = resolver.resolve(
            topic=topic,
            instructions=instructions,
            academic_mode=academic_mode,
            language=language,
            artifact_override=artifact_override,
        )
        return resolved.metadata()
    except Exception as exc:
        logging.getLogger(__name__).warning("Prompt enhancement metadata resolution skipped: %s", exc)
        return {}


@app.post("/api/prompt/enhance", response_model=PromptEnhanceResponse)
async def enhance_prompt(payload: PromptEnhanceRequest):
    """
    Uses the example_generator agent to enhance a raw topic and instructions
    into a clearer genre-preserving writing task.
    """
    from academic_pe.agents.factory import create_agent

    try:
        config = load_config("config/agents.yaml")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load configuration: {str(e)}")

    agent_cfg = config.agents.get("brief_normalizer") or config.agents.get("example_generator")
    if not agent_cfg:
        raise HTTPException(status_code=500, detail="brief_normalizer agent configuration not found in agents.yaml")

    lang = config.ui.language

    prompt = _build_brief_normalization_prompt(
        payload.topic,
        payload.instructions,
        lang,
        academic_mode=payload.academic_mode if payload.academic_mode is not None else config.pipeline.academic_mode,
        artifact_override=payload.artifact_override,
    )

    loop = asyncio.get_running_loop()

    def run_agent():
        agent = create_agent(
            "brief_normalizer",
            agent_cfg,
            retry_cfg=config.retry,
            cb_cfg=config.circuit_breaker,
            agent_type="brief_normalizer"
        )
        return agent.process(prompt), agent.last_self_critique_summary

    try:
        raw_response, self_critique_summary = await loop.run_in_executor(None, run_agent)
        enhanced_topic, enhanced_instructions, fallback_used = _normalize_prompt_enhancement_response(
            raw_response,
            fallback_topic=payload.topic,
            fallback_instructions=payload.instructions,
        )

        effective_academic_mode = (
            payload.academic_mode if payload.academic_mode is not None else config.pipeline.academic_mode
        )
        artifact_metadata = _resolve_prompt_enhancement_metadata(
            topic=enhanced_topic,
            instructions=enhanced_instructions,
            academic_mode=effective_academic_mode,
            language=lang,
            artifact_override=payload.artifact_override,
        )
        if fallback_used:
            summary = self_critique_summary or ""
            self_critique_summary = (
                f"{summary} Prompt enhancement fell back to the original non-empty fields."
            ).strip()

        return PromptEnhanceResponse(
            topic=enhanced_topic,
            instructions=enhanced_instructions,
            self_critique_summary=self_critique_summary,
            artifact_override=payload.artifact_override,
            resolved_manifest=artifact_metadata.get("resolved_manifest"),
            resolved_contract=artifact_metadata.get("resolved_contract"),
            contract_sexpr=artifact_metadata.get("contract_sexpr"),
            manifest_selection=artifact_metadata.get("manifest_selection"),
            decision_summary=artifact_metadata.get("decision_summary"),
        )

    except Exception as e:
        logging.getLogger(__name__).exception("Failed to enhance prompt: %s", e)
        raise HTTPException(status_code=500, detail=f"Prompt enhancement failed: {str(e)}")



@app.get("/api/templates")
def get_templates():
    try:
        library = TemplateLibrary.from_yaml("config/document_templates.yaml")
        return [
            {
                "id": template.id,
                "name": template.name,
                "description": template.description,
                "category": template.category,
                "language_policy": template.language_policy.value,
                "section_count": len(template.sections),
            }
            for template in library.list_templates()
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read document templates: {str(e)}")


@app.post("/api/config")
def update_config(payload: ConfigUpdateRequest):
    config_path = "config/agents.yaml"
    try:
        # Validate against AppConfig structure
        AppConfig(**payload.config)
        
        # Write back to yaml
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(payload.config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            
        return {"status": "success", "message": "Configuration updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid configuration or validation error: {str(e)}")

@app.get("/api/status")
def get_status():
    with run_lock:
        return current_run


@app.get("/api/status/stream")
async def status_stream():
    async def event_generator():
        last_payload = None
        while True:
            with run_lock:
                payload = json.dumps(dict(current_run), ensure_ascii=False, default=str)
                running = current_run.get("status") == "RUNNING"

            if payload != last_payload:
                yield f"data: {payload}\n\n"
                last_payload = payload

            if not running:
                await asyncio.sleep(1.5)
            else:
                await asyncio.sleep(0.25)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

class InterceptingDict(dict):
    def __init__(self, callback, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.callback = callback

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.callback(self)

def run_pipeline_thread(
    topic: str,
    instructions: Optional[str],
    template_mode: Optional[TemplateMode] = None,
    template_id: Optional[str] = None,
    academic_mode: Optional[bool] = None,
    run_id: Optional[str] = None,
    author: Optional[str] = None,
    continuation_source: Optional[dict] = None,
    artifact_override: Optional[str] = None,
    web_search_enabled: bool = False,
    attachments: Optional[List[dict]] = None,
):
    global current_run, _current_orchestrator
    
    # Configure logging capturing
    status_handler = StatusLogHandler(current_run["logs"])
    root_logger.addHandler(status_handler)
    
    success = False
    try:
        # Load local configuration
        config = load_config("config/agents.yaml")
        if template_mode is not None:
            config.pipeline.template_mode = template_mode
        if template_id is not None:
            config.pipeline.template_id = template_id
        if academic_mode is not None:
            config.pipeline.academic_mode = academic_mode
        if run_id:
            config.pipeline.output_dir = os.path.join("exports", run_id)
            os.makedirs(config.pipeline.output_dir, exist_ok=True)

        # Resolve continuation source from attachments if uploaded
        if not continuation_source and attachments:
            continuation_attachment = next((a for a in attachments if a.get("attachment_type") == "continuation_source"), None)
            if continuation_attachment:
                from academic_pe.core.ocr import split_markdown_into_sections
                content = continuation_attachment.get("content", "")
                filename = continuation_attachment.get("filename", "Uploaded Document")
                context_data, runtime_tpl = split_markdown_into_sections(content)
                continuation_source = {
                    "source_type": "uploaded",
                    "topic": filename,
                    "instructions": instructions or "",
                    "context": context_data,
                    "runtime_template": runtime_tpl,
                    "template_mode": "custom",
                    "filename": filename,
                    "content": content,
                    "attachment_type": "continuation_source",
                    "token_count": continuation_attachment.get("token_count"),
                }

        # Sift reference materials
        reference_materials = []
        if attachments:
            reference_materials = [
                {
                    "filename": a["filename"],
                    "content": a["content"],
                    "attachment_type": a.get("attachment_type"),
                    "token_count": a.get("token_count"),
                }
                for a in attachments
                if a.get("attachment_type") in {"passive_reference", "style_sample"}
            ]

        config = _apply_continuation_structure(config, continuation_source)
        with run_lock:
            current_run["template_mode"] = config.pipeline.template_mode.value
            current_run["template_id"] = config.pipeline.template_id
            current_run["academic_mode"] = config.pipeline.academic_mode
            current_run["document_plan"] = None
            current_run["continuation_source"] = continuation_source
            current_run["artifact_override"] = artifact_override

        # Apply legacy section-topic overrides only for the current custom structure.
        # Fixed templates must remain structurally bound to the selected template.
        if topic and config.pipeline.template_mode == TemplateMode.custom and not continuation_source:
            with run_lock:
                current_run["topic"] = topic
                current_run["instructions"] = instructions
            for sec in config.pipeline.sections:
                if sec.name == "theory":
                    sec.topic = f"{topic}: Theoretical Foundations"
                elif sec.name == "calculation":
                    sec.topic = f"{topic}: Quantitative Analysis & Models"
                elif sec.name == "conclusion":
                    sec.topic = f"{topic}: Summary & Outlook"
                else:
                    sec.topic = f"{topic}: {sec.topic}"
                
                if instructions:
                    sec.instruction = f"{sec.instruction} Guideline: {instructions}"

        # Initialize orchestrator. Draft generation no longer renders DOCX;
        # export happens only through /api/export/docx.
        orch = create_orchestrator_from_config(
            config,
            user_topic=topic or "",
            user_instructions=instructions or "",
            continuation_source=continuation_source,
            artifact_override=artifact_override,
            reference_materials=reference_materials,
            web_search_enabled=web_search_enabled,
            registry_store=registry_store,
        )
        with run_lock:
            current_run["topic"] = orch.user_topic
            current_run["runtime_template"] = (
                orch.runtime_template.model_dump(mode="json")
                if orch.runtime_template is not None
                else None
            )
            current_run["runtime_prompt_manifest"] = (
                orch.runtime_prompt_manifest.model_dump(mode="json")
                if orch.runtime_prompt_manifest is not None
                else None
            )
            artifact_metadata = _artifact_manifest_metadata(current_run["runtime_prompt_manifest"])
            current_run["resolved_manifest"] = artifact_metadata.get("resolved_manifest")
            current_run["resolved_contract"] = artifact_metadata.get("resolved_contract")
            current_run["contract_sexpr"] = artifact_metadata.get("contract_sexpr")
            current_run["manifest_selection"] = artifact_metadata.get("manifest_selection")
            current_run["decision_summary"] = artifact_metadata.get("decision_summary")
            editorial_metadata = _editorial_runtime_metadata(current_run["runtime_prompt_manifest"])
            current_run["continuation_intent"] = editorial_metadata.get("continuation_intent")
            current_run["document_state"] = editorial_metadata.get("document_state")
            current_run["edit_plan"] = editorial_metadata.get("edit_plan")
        
        # Store orchestrator for cancellation
        with _orchestrator_lock:
            _current_orchestrator = orch
        
        # Intercept context modifications to update current_run safely in real time
        def on_context_change(d):
            with run_lock:
                current_run["context"] = dict(d)
                if "document_plan" in d:
                    current_run["document_plan"] = d["document_plan"]

        def on_section_delta(section_name: str, delta: str, accumulated: str):
            with run_lock:
                current_context = current_run.get("context")
                context = dict(current_context) if isinstance(current_context, dict) else {}
                context[section_name] = accumulated
                current_run["context"] = context
                current_run["active_section"] = section_name
                if section_name == "document_plan":
                    current_run["document_plan"] = accumulated
        orch.context = InterceptingDict(on_context_change)
        
        # Set transition hooks
        def on_enter_hook(old_state, new_state):
            with run_lock:
                current_run["state"] = new_state.name
                current_run["logs"].append(f"[FSM] Entering state: {new_state.name}")
                if new_state.name == "REVIEWING" and not current_run.get("original_context"):
                    current_context = current_run.get("context")
                    current_run["original_context"] = dict(current_context) if isinstance(current_context, dict) else {}
            
        def on_exit_hook(old_state, new_state):
            with run_lock:
                current_run["logs"].append(f"[FSM] Exiting state: {old_state.name}")
            
        orch.on_enter(on_enter_hook)
        orch.on_exit(on_exit_hook)
        orch.on_section_delta(on_section_delta)
        
        # Intercept review decisions for progress logs
        orig_reviewer_process = None
        if orch._reviewer:
            orig_process = orch._reviewer.process
            def logged_reviewer_process(
                task_description: str,
                context: Optional[str] = None,
                on_delta: Optional[Callable[[str], None]] = None,
                document_sections: Optional[Dict[str, str]] = None,
            ) -> str:
                res = orig_process(
                    task_description,
                    context=context,
                    on_delta=on_delta,
                    document_sections=document_sections,
                )
                with run_lock:
                    current_run["reviewer_feedback"].append(res)
                    current_run["logs"].append(f"[Reviewer Feedback]: {res}")
                return res
            orch._reviewer.process = logged_reviewer_process

        # Run pipeline
        output_path = orch.run_pipeline(render_artifact=False)
        
        # Update current context preview
        with run_lock:
            current_run["context"] = dict(orch.context)
            current_run["runtime_template"] = (
                orch.runtime_template.model_dump(mode="json")
                if orch.runtime_template is not None
                else current_run.get("runtime_template")
            )
            current_run["runtime_prompt_manifest"] = (
                orch.runtime_prompt_manifest.model_dump(mode="json")
                if orch.runtime_prompt_manifest is not None
                else current_run.get("runtime_prompt_manifest")
            )
            editorial_metadata = _editorial_runtime_metadata(current_run["runtime_prompt_manifest"])
            current_run["continuation_intent"] = editorial_metadata.get("continuation_intent")
            current_run["document_state"] = editorial_metadata.get("document_state")
            current_run["edit_plan"] = editorial_metadata.get("edit_plan")
            current_run["merge_patch"] = editorial_metadata.get("merge_patch")
            current_run["document_ledger"] = orch._document_ledger.model_dump(mode="json")
            current_run["calculation_ledger"] = orch._calculation_ledger.model_dump(mode="json")
            current_run["docx_filename"] = os.path.basename(output_path) if output_path else None
            current_run["export_report"] = None
            current_run["status"] = "COMPLETED"
            current_run["state"] = "DONE"
            current_run["active_section"] = None
        
        # Save history metadata
        metadata_dir = os.path.join("exports", "_metadata")
        os.makedirs(metadata_dir, exist_ok=True)
        metadata_stem = Path(output_path).stem
        if not metadata_stem and run_id:
            metadata_stem = run_id
        metadata_filename = os.path.join(
            metadata_dir,
            f"{metadata_stem}.{datetime.now().strftime('%Y%m%d%H%M%S')}.metadata.json",
        )
        metadata = _with_artifact_manifest_metadata({
            "topic": topic,
            "instructions": instructions,
            "previous_prompt": _build_previous_prompt(topic, instructions),
            "author": author,
            "run_id": run_id,
            "continuation_source": continuation_source,
            "artifact_override": artifact_override,
            "template_mode": config.pipeline.template_mode.value,
            "template_id": config.pipeline.template_id,
            "runtime_template": (
                orch.runtime_template.model_dump(mode="json")
                if orch.runtime_template is not None
                else None
            ),
            "runtime_prompt_manifest": (
                orch.runtime_prompt_manifest.model_dump(mode="json")
                if orch.runtime_prompt_manifest is not None
                else None
            ),
            "timestamp": current_run["timestamp"],
            "status": "COMPLETED",
            "docx_filename": os.path.basename(output_path) if output_path else None,
            "context": orch.context,
            "document_plan": current_run.get("document_plan"),
            "self_critique_summary": orch.self_critique_summaries,
            "original_context": current_run.get("original_context", {}),
            "academic_mode": config.pipeline.academic_mode,
            "logs": current_run["logs"],
            "reviewer_feedback": current_run["reviewer_feedback"],
            "continuation_intent": current_run.get("continuation_intent"),
            "document_state": current_run.get("document_state"),
            "edit_plan": current_run.get("edit_plan"),
            "merge_patch": current_run.get("merge_patch"),
            "document_ledger": current_run.get("document_ledger"),
            "calculation_ledger": current_run.get("calculation_ledger"),
        })
        from academic_pe.core.revision import initialize_revision_history
        initialize_revision_history(metadata)
        with open(metadata_filename, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        try:
            from academic_pe.core.registry import import_metadata_json
            import_metadata_json(registry_store, metadata_filename)
        except Exception as ree:
            logging.getLogger(__name__).warning("Failed to sync completed run metadata to SQLite registry: %s", ree)
        success = True
            
    except PipelineCancelled:
        with run_lock:
            current_run["status"] = "CANCELLED"
            current_run["state"] = "CANCELLED"
            current_run["logs"].append("[FSM] Pipeline cancelled by user")
            current_run["active_section"] = None
        logging.getLogger(__name__).info("Pipeline cancelled by user request")
    except Exception as e:
        with run_lock:
            current_run["status"] = "FAILED"
            current_run["state"] = "FAILED"
            current_run["error"] = str(e)
            current_run["logs"].append(f"[Error]: {str(e)}")
            current_run["active_section"] = None
        logging.getLogger(__name__).exception("Pipeline background execution failed")
    finally:
        if run_id:
            _cleanup_run_directory(run_id, success)
        with _orchestrator_lock:
            _current_orchestrator = None
        root_logger.removeHandler(status_handler)

@app.post("/api/run")
def run_pipeline(payload: RunRequest, background_tasks: BackgroundTasks):
    global current_run
    
    with run_lock:
        if current_run["status"] == "RUNNING":
            raise HTTPException(status_code=400, detail="A pipeline is already executing")
            
        # Generate unique run_id
        run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Reset current run status
        current_run["status"] = "RUNNING"
        current_run["state"] = "INIT"
        current_run["logs"] = [f"Pipeline run triggered at {datetime.now().isoformat()}"]
        current_run["context"] = {}
        current_run["original_context"] = {}
        current_run["reviewer_feedback"] = []
        current_run["docx_filename"] = None
        current_run["pdf_filename"] = None
        current_run["export_report"] = None
        current_run["error"] = None
        current_run["topic"] = payload.topic
        current_run["instructions"] = payload.instructions
        current_run["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        current_run["author"] = payload.author
        current_run["active_section"] = None
        current_run["template_mode"] = (
            payload.template_mode.value if payload.template_mode is not None else None
        )
        current_run["template_id"] = payload.template_id
        current_run["runtime_template"] = None
        current_run["runtime_prompt_manifest"] = None
        current_run["academic_mode"] = (
            payload.academic_mode if payload.academic_mode is not None else False
        )
        current_run["run_id"] = run_id
        current_run["document_plan"] = None
        current_run["resolved_manifest"] = None
        current_run["resolved_contract"] = None
        current_run["contract_sexpr"] = None
        current_run["manifest_selection"] = None
        current_run["decision_summary"] = None
        current_run["continuation_source"] = (
            payload.continuation_source.model_dump(mode="json")
            if payload.continuation_source is not None
            else None
        )
        current_run["artifact_override"] = payload.artifact_override
        current_run["continuation_intent"] = None
        current_run["document_state"] = None
        current_run["edit_plan"] = None
        current_run["merge_patch"] = None
        current_run["revisions"] = []
        current_run["document_ledger"] = None
        current_run["calculation_ledger"] = None

    background_tasks.add_task(
        run_pipeline_thread,
        payload.topic,
        payload.instructions,
        payload.template_mode,
        payload.template_id,
        payload.academic_mode,
        run_id,
        payload.author,
        (
            payload.continuation_source.model_dump(mode="json")
            if payload.continuation_source is not None
            else None
        ),
        payload.artifact_override,
        payload.web_search_enabled or False,
        [a.model_dump() for a in payload.attachments] if payload.attachments else None,
    )
    return {"status": "started", "message": "Pipeline execution started in the background"}


def _run_revision_thread(metadata_path: str, request, revision_number: int) -> None:
    """Execute a queued revision without routing it through full generation."""
    from academic_pe.core.calculation_audit import CalculationLedger
    from academic_pe.core.document_ledger import DocumentLedger
    from academic_pe.core.document_state import extract_document_state
    from academic_pe.core.revision import (
        DocumentRevision,
        append_revision,
        execute_patch_revision,
        revision_history,
    )

    try:
        with open(metadata_path, "r", encoding="utf-8") as file:
            metadata = json.load(file)
        history = revision_history(metadata)
        pending = next(item for item in history if item.revision == revision_number and item.status == "queued")
        ready = [item for item in history if item.status == "ready"]
        parent = max(ready, key=lambda item: item.revision)
        running = pending.model_copy(update={"status": "running"})
        append_revision(metadata, running)
        _write_history_metadata(metadata_path, metadata)

        config = _apply_continuation_structure(load_config("config/agents.yaml"), {
            "context": parent.context_snapshot,
            "runtime_template": metadata.get("runtime_template"),
        })
        continuation_source = {
            "source_type": "generated",
            "topic": metadata.get("topic"),
            "instructions": metadata.get("instructions"),
            "context": parent.context_snapshot,
            "runtime_template": metadata.get("runtime_template"),
            "runtime_prompt_manifest": metadata.get("runtime_prompt_manifest"),
            "intent_override": "revise_in_place",
        }
        orch = create_orchestrator_from_config(
            config,
            user_topic=str(metadata.get("topic") or ""),
            user_instructions=request.feedback,
            continuation_source=continuation_source,
            registry_store=registry_store,
        )
        result = execute_patch_revision(
            request=request,
            config=config,
            writer=orch._writer,
            context=parent.context_snapshot,
            runtime_template=metadata.get("runtime_template"),
            runtime_prompt_manifest=metadata.get("runtime_prompt_manifest"),
            document_ledger=(
                DocumentLedger.model_validate(metadata["document_ledger"])
                if isinstance(metadata.get("document_ledger"), dict)
                else None
            ),
            calculation_ledger=(
                CalculationLedger.model_validate(metadata["calculation_ledger"])
                if isinstance(metadata.get("calculation_ledger"), dict)
                else None
            ),
            reviewer=orch._reviewer,
            evidence_reviewer=orch._evidence_reviewer,
            editorial_reviewer=orch._editorial_reviewer,
        )
        completed = running.model_copy(update={
            "status": "ready",
            "changed_sections": result.changed_sections,
            "change_summary": (
                "No content changes were required."
                if not result.changed_sections
                else "Patched section(s): " + ", ".join(result.changed_sections)
            ),
            "context_snapshot": result.context,
        })
        metadata["context"] = result.context
        metadata["revision_plan"] = result.plan.model_dump(mode="json")
        metadata["document_state"] = extract_document_state({
            "context": result.context,
            "runtime_template": metadata.get("runtime_template"),
            "runtime_prompt_manifest": metadata.get("runtime_prompt_manifest"),
        }).model_dump(mode="json")
        append_revision(metadata, completed)
        _write_history_metadata(metadata_path, metadata)
        with run_lock:
            current_run.update({
                "status": "COMPLETED",
                "state": "DONE",
                "context": result.context,
                "document_state": metadata["document_state"],
                "revisions": metadata["revisions"],
                "document_ledger": metadata.get("document_ledger"),
                "calculation_ledger": metadata.get("calculation_ledger"),
                "active_section": None,
            })
            current_run["logs"].append(f"[Revision] Version {completed.revision} is ready.")
    except Exception as exc:
        logging.getLogger(__name__).exception("Revision execution failed")
        try:
            with open(metadata_path, "r", encoding="utf-8") as file:
                metadata = json.load(file)
            history = revision_history(metadata)
            for item in history:
                if item.revision == revision_number and item.status in {"queued", "running"}:
                    append_revision(metadata, item.model_copy(update={"status": "failed", "change_summary": str(exc)}))
                    break
            _write_history_metadata(metadata_path, metadata)
        except Exception:
            logging.getLogger(__name__).exception("Failed to record revision failure")
        with run_lock:
            current_run.update({"status": "FAILED", "state": "FAILED", "error": str(exc), "active_section": None})
            current_run["logs"].append(f"[Revision Error] {exc}")


@app.get("/api/runs/{run_id}/revisions")
def list_revisions(run_id: str):
    from academic_pe.core.revision import revision_history
    _, metadata = _metadata_for_run_id(run_id)
    return [item.model_dump(mode="json") for item in revision_history(metadata)]


@app.get("/api/runs/{run_id}/revisions/{revision}")
def get_revision(run_id: str, revision: int):
    from academic_pe.core.revision import revision_history
    _, metadata = _metadata_for_run_id(run_id)
    for item in revision_history(metadata):
        if item.revision == revision:
            return item.model_dump(mode="json")
    raise HTTPException(status_code=404, detail="Revision not found")


@app.post("/api/runs/{run_id}/revisions")
def create_revision(run_id: str, payload: RevisionCreateRequest, background_tasks: BackgroundTasks):
    """Queue a user-requested revision of a ready document version."""
    from academic_pe.core.revision import DocumentRevision, RevisionRequest, append_revision, build_revision_plan, revision_history

    with run_lock:
        if current_run["status"] == "RUNNING":
            raise HTTPException(status_code=409, detail="A pipeline or revision is already executing")
    metadata_path, metadata = _metadata_for_run_id(run_id)
    history = revision_history(metadata)
    ready = [item for item in history if item.status == "ready"]
    if not ready:
        raise HTTPException(status_code=409, detail="The document has no ready revision")
    base = max(ready, key=lambda item: item.revision)
    if payload.base_revision != base.revision:
        raise HTTPException(status_code=409, detail=f"base_revision must be the current ready revision ({base.revision})")
    request = RevisionRequest(
        run_id=run_id,
        base_revision=payload.base_revision,
        feedback=payload.feedback,
        affected_sections=payload.affected_sections,
    )
    try:
        plan = build_revision_plan(request, base.context_snapshot, metadata.get("runtime_template"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    next_revision = max(item.revision for item in history) + 1
    pending = DocumentRevision(
        run_id=run_id,
        revision=next_revision,
        parent_revision=base.revision,
        trigger="user_feedback",
        feedback=request.feedback,
        changed_sections=[],
        change_summary="Revision request accepted; patch planning is queued.",
    )
    append_revision(metadata, pending)
    _write_history_metadata(metadata_path, metadata)
    with run_lock:
        current_run.update({
            "status": "RUNNING",
            "state": "REVISING",
            "run_id": run_id,
            "context": base.context_snapshot,
            "revisions": metadata["revisions"],
            "error": None,
        })
        current_run["logs"].append(f"[Revision] Queued version {next_revision} from version {base.revision}.")
    background_tasks.add_task(_run_revision_thread, metadata_path, request, next_revision)
    response = pending.model_dump(mode="json")
    response["plan"] = plan.model_dump(mode="json")
    return response


@app.post("/api/attachments/upload")
async def upload_attachment(
    file: UploadFile = File(...),
    attachment_type: str = Form("passive_reference")
):
    if attachment_type not in {"passive_reference", "continuation_source", "style_sample"}:
        raise HTTPException(
            status_code=400,
            # Preserve the stable public error text used by older clients.
            detail="attachment_type must be 'passive_reference' or 'continuation_source'",
        )

    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {e}")

    filename = file.filename or "uploaded_file"
    try:
        # Starlette/FastAPI decodes multipart filenames as latin-1.
        # We recover the original UTF-8 bytes.
        filename = filename.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass

    ext = os.path.splitext(filename)[1].lower()
    allowed_extensions = (
        CONTINUATION_ATTACHMENT_EXTENSIONS
        if attachment_type == "continuation_source"
        else REFERENCE_ATTACHMENT_EXTENSIONS
    )
    if ext not in allowed_extensions:
        allowed_label = ", ".join(sorted(allowed_extensions))
        if attachment_type == "continuation_source":
            detail = (
                f"Unsupported continuation source format: {ext or 'no extension'}. "
                f"Allowed formats: {allowed_label}."
            )
        else:
            detail = (
                f"Unsupported reference attachment format: {ext or 'no extension'}. "
                f"Allowed formats: {allowed_label}."
            )
        raise HTTPException(status_code=400, detail=detail)
    
    mime_type = file.content_type or "application/octet-stream"

    # 1. Process/parse the file
    from academic_pe.core.ocr import parse_document
    try:
        content = parse_document(filename, file_bytes, mime_type)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 2. Count tokens using tiktoken (o200k_base)
    from academic_pe.core.ocr import count_tokens
    token_count = count_tokens(content)

    # 3. Check token guardrail
    config = load_config("config/agents.yaml")
    token_limit = getattr(config, "ocr_token_limit", 20000)

    if token_count > token_limit:
        raise HTTPException(
            status_code=400,
            detail=f"File '{filename}' exceeds the configured token limit of {token_limit} tokens (contains {token_count} tokens)."
        )

    return {
        "filename": filename,
        "content": content,
        "attachment_type": attachment_type,
        "token_count": token_count
    }


@app.post("/api/cancel")
def cancel_pipeline():
    global _current_orchestrator
    
    with _orchestrator_lock:
        if _current_orchestrator is None:
            raise HTTPException(status_code=400, detail="No pipeline is currently running")
        
        _current_orchestrator.cancel()
    
    return {"status": "cancelling", "message": "Pipeline cancellation requested"}


@app.get("/api/export/prerequisites")
def export_prerequisites():
    discovery = discover_soffice()
    return {
        "libreoffice": {
            "available": discovery.available,
            "executable": discovery.executable,
            "source": discovery.source,
            "install_hint": discovery.install_hint,
        }
    }


def _prepare_export(payload: ExportRequest):
    global current_run
    run_id = None
    source_document_plan = None
    author = payload.author
    if payload.context:
        context = dict(payload.context)
        source_document_plan = context.get("document_plan")
        topic = payload.topic or "Untitled"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with run_lock:
            if author is None:
                current_author = current_run.get("author")
                author = current_author if isinstance(current_author, str) else None
            val = payload.run_id or current_run.get("run_id")
            if isinstance(val, str):
                run_id = val
    else:
        with run_lock:
            if current_run["status"] == "RUNNING":
                raise HTTPException(status_code=400, detail="Cannot export while generation is still running")
            current_context = current_run.get("context")
            context = dict(current_context) if isinstance(current_context, dict) else {}
            source_document_plan = current_run.get("document_plan") or context.get("document_plan")
            topic = str(current_run.get("topic") or "Untitled")
            timestamp = str(current_run.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            if author is None:
                current_author = current_run.get("author")
                author = current_author if isinstance(current_author, str) else None
            val = payload.run_id or current_run.get("run_id")
            if isinstance(val, str):
                run_id = val

    with run_lock:
        if not payload.context and current_run["status"] == "RUNNING":
            raise HTTPException(status_code=400, detail="Cannot export while generation is still running")

    if not context:
        raise HTTPException(status_code=400, detail="No draft content is available to export")

    if run_id is not None and not _is_valid_run_id(run_id):
        raise HTTPException(status_code=400, detail="Invalid run_id")

    export_context = _exportable_context(context)
    if not export_context:
        raise HTTPException(status_code=400, detail="No exportable draft sections are available")

    config = load_config("config/agents.yaml")
    if isinstance(run_id, str):
        config.pipeline.output_dir = os.path.join("exports", run_id)
        os.makedirs(config.pipeline.output_dir, exist_ok=True)

    # Resolve runtime template from payload or current run
    rt_data: Optional[dict] = None
    if payload.runtime_template:
        rt_data = payload.runtime_template
    else:
        with run_lock:
            current_rt = current_run.get("runtime_template")
            if isinstance(current_rt, dict):
                rt_sections = current_rt.get("sections")
                if isinstance(rt_sections, list):
                    # Fallback to current_run's template if context matches or is not payload-supplied
                    if not payload.context or any(
                        isinstance(sec, dict) and sec.get("name") in export_context
                        for sec in rt_sections
                    ):
                        rt_data = current_rt

    if isinstance(rt_data, dict):
        try:
            from academic_pe.core.templates import RuntimeTemplate
            from academic_pe.core.orchestrator import _apply_runtime_template
            runtime_template = RuntimeTemplate(**rt_data)
            terminal_section_names = _terminal_section_names_from_runtime_template_data(rt_data)
            hidden_section_names = {
                section.name
                for section in runtime_template.sections
                if not is_renderable_section(section)
            }
            if hidden_section_names:
                export_context = {
                    key: value
                    for key, value in export_context.items()
                    if key not in hidden_section_names
                }
            export_context = _move_terminal_export_sections_to_end(export_context, terminal_section_names)
            config = _apply_runtime_template(config, runtime_template)
            config = _align_config_sections_to_export_context(config, export_context)
            config.pipeline.title = topic
        except Exception as e:
            logging.getLogger(__name__).warning("Failed to apply runtime template in export: %s", e)
    else:
        # Dynamic fallback: if no template is provided, but context contains different keys,
        # create section prompts dynamically so they are not ignored.
        default_section_names = {sec.name for sec in config.pipeline.sections}
        context_keys = list(export_context.keys())
        if not all(key in default_section_names for key in context_keys):
            from academic_pe.core.config import SectionPrompt
            new_sections: List[SectionPrompt] = []
            for key in context_keys:
                existing = next((sec for sec in config.pipeline.sections if sec.name == key), None)
                if existing:
                    new_sections.append(existing)
                else:
                    new_sections.append(SectionPrompt(
                        name=key,
                        topic=key.replace("_", " ").title(),
                        instruction=""
                    ))
            config.pipeline.sections = new_sections
        terminal_section_names = [
            key
            for key in export_context
            if is_terminal_section_name(key)
        ]
        export_context = _move_terminal_export_sections_to_end(export_context, terminal_section_names)
        config = _align_config_sections_to_export_context(config, export_context)
        config.pipeline.title = topic

    return export_context, config, topic, timestamp, author, run_id, source_document_plan


def _write_export_metadata(
    result,
    config,
    topic: str,
    timestamp: str,
    author: Optional[str],
    source_document_plan,
    export_context,
    run_id: Optional[str],
) -> None:
    revision_metadata_path = None
    if isinstance(run_id, str) and _is_valid_run_id(run_id):
        try:
            revision_metadata_path, _ = _metadata_for_run_id(run_id)
        except HTTPException:
            pass
    metadata_dir = os.path.join("exports", "_metadata")
    os.makedirs(metadata_dir, exist_ok=True)
    metadata_filename = os.path.join(
        metadata_dir,
        f"{Path(result.filename).stem}.{datetime.now().strftime('%Y%m%d%H%M%S')}.metadata.json",
    )
    metadata = _with_artifact_manifest_metadata({
        "topic": topic,
        "instructions": current_run.get("instructions"),
        "previous_prompt": _build_previous_prompt(topic, current_run.get("instructions")),
        "author": author,
        "run_id": run_id,
        "template_mode": current_run.get("template_mode") or config.pipeline.template_mode.value,
        "template_id": current_run.get("template_id") or config.pipeline.template_id,
        "runtime_template": current_run.get("runtime_template"),
        "runtime_prompt_manifest": current_run.get("runtime_prompt_manifest"),
        "artifact_override": current_run.get("artifact_override"),
        "timestamp": timestamp,
        "status": "COMPLETED",
        "docx_filename": result.filename if result.filename.lower().endswith(".docx") else current_run.get("docx_filename"),
        "pdf_filename": result.filename if result.filename.lower().endswith(".pdf") else current_run.get("pdf_filename"),
        "context": export_context,
        "document_plan": current_run.get("document_plan") or source_document_plan,
        "original_context": current_run.get("original_context", {}),
        "academic_mode": current_run.get("academic_mode") or config.pipeline.academic_mode,
        "logs": current_run.get("logs", []),
        "reviewer_feedback": current_run.get("reviewer_feedback", []),
        "export_report": result.to_dict(),
        "continuation_intent": current_run.get("continuation_intent"),
        "document_state": current_run.get("document_state"),
        "edit_plan": current_run.get("edit_plan"),
        "merge_patch": current_run.get("merge_patch"),
        "document_ledger": current_run.get("document_ledger"),
        "calculation_ledger": current_run.get("calculation_ledger"),
        "revisions": current_run.get("revisions", []),
    })
    from academic_pe.core.revision import initialize_revision_history
    initialize_revision_history(metadata)
    with open(metadata_filename, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    if revision_metadata_path:
        try:
            from academic_pe.core.revision import append_revision, revision_history
            with open(revision_metadata_path, "r", encoding="utf-8") as file:
                revision_metadata = json.load(file)
            ready = [item for item in revision_history(revision_metadata) if item.status == "ready"]
            if ready:
                latest = max(ready, key=lambda item: item.revision)
                append_revision(
                    revision_metadata,
                    latest.model_copy(update={"artifact_path": result.filename}),
                )
                _write_history_metadata(revision_metadata_path, revision_metadata)
                with run_lock:
                    if current_run.get("run_id") == run_id:
                        current_run["revisions"] = revision_metadata["revisions"]
        except Exception as exc:
            logging.getLogger(__name__).warning("Failed to link export to document revision: %s", exc)


@app.post("/api/export/docx")
def export_docx(payload: ExportRequest):
    global current_run
    export_context, config, topic, timestamp, author, run_id, source_document_plan = _prepare_export(payload)

    try:
        result = export_docx_with_qa(export_context, config, output_filename=payload.filename)
    except PermissionError:
        raise HTTPException(
            status_code=400,
            detail=(
                "РќРµ СѓРґР°Р»РѕСЃСЊ СЃРѕС…СЂР°РЅРёС‚СЊ РґРѕРєСѓРјРµРЅС‚. Р¤Р°Р№Р» РѕС‚РєСЂС‹С‚ РІ РґСЂСѓРіРѕР№ РїСЂРѕРіСЂР°РјРјРµ (РЅР°РїСЂРёРјРµСЂ, Microsoft Word) "
                "Рё Р·Р°Р±Р»РѕРєРёСЂРѕРІР°РЅ. РџРѕР¶Р°Р»СѓР№СЃС‚Р°, Р·Р°РєСЂРѕР№С‚Рµ РµРіРѕ Рё РїРѕРїСЂРѕР±СѓР№С‚Рµ СЃРЅРѕРІР°. / "
                "Failed to save document. The file is open in another program (like Microsoft Word) and locked. "
                "Please close it and try again."
            )
        )

    if run_id:
        result.filename = f"{run_id}/{result.filename}"

    with run_lock:
        if not payload.context:
            current_run["docx_filename"] = result.filename
            current_run["export_report"] = result.to_dict()
        logs_list = current_run.get("logs")
        if isinstance(logs_list, list):
            logs_list.append(f"[Export QA]: {result.status.upper()} for {result.filename}")

    _write_export_metadata(result, config, topic, timestamp, author, source_document_plan, export_context, run_id)

    return result.to_dict()


@app.post("/api/export/pdf")
def export_pdf(payload: ExportRequest):
    global current_run
    export_context, config, topic, timestamp, author, run_id, source_document_plan = _prepare_export(payload)

    result = export_pdf_with_qa(export_context, config, output_filename=payload.filename)
    if result.status == "failed":
        detail = result.issues[0].message if result.issues else "PDF export failed"
        raise HTTPException(status_code=503, detail=detail)

    if run_id:
        result.filename = f"{run_id}/{result.filename}"

    with run_lock:
        if not payload.context:
            current_run["pdf_filename"] = result.filename
            current_run["export_report"] = result.to_dict()
        logs_list = current_run.get("logs")
        if isinstance(logs_list, list):
            logs_list.append(f"[PDF Export]: {result.status.upper()} for {result.filename}")

    _write_export_metadata(result, config, topic, timestamp, author, source_document_plan, export_context, run_id)

    return result.to_dict()

@app.get("/api/download/{filename:path}")
def download_file(filename: str):
    output_dir = _pipeline_output_dir()
        
    file_path = os.path.abspath(os.path.join(output_dir, filename))
    abs_output_dir = os.path.abspath(output_dir)
    if not file_path.startswith(abs_output_dir):
        raise HTTPException(status_code=403, detail="Access denied")
        
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File {filename} not found")
        
    download_name = os.path.basename(file_path)
    media_type = (
        "application/pdf"
        if download_name.lower().endswith(".pdf")
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    return FileResponse(file_path, filename=download_name, media_type=media_type)

@app.get("/api/history")
def get_history(archived: Optional[bool] = None, include_archived: bool = False):
    from academic_pe.core.registry import NoopRegistryStore
    
    # Try reading from registry if available
    if not isinstance(registry_store, NoopRegistryStore):
        try:
            # Load all generation runs
            runs = registry_store.list_runs(kind="generation", limit=1000)
            history = []
            output_dir = _pipeline_output_dir()

            def artifact_size(artifact: Any, filename: Optional[str], run_id: str) -> Optional[int]:
                if artifact is not None and artifact.size_bytes is not None:
                    return artifact.size_bytes
                if not filename:
                    return None
                try:
                    for candidate in (os.path.join(output_dir, filename), os.path.join(output_dir, run_id, filename)):
                        if os.path.isfile(candidate):
                            return os.path.getsize(candidate)
                except OSError:
                    pass
                return None
            
            for run in runs:
                # Load metadata_json
                meta = {}
                if run.metadata_json:
                    try:
                        meta = json.loads(run.metadata_json)
                    except Exception:
                        pass
                meta = _hydrate_registry_metadata(meta)
                
                is_archived = bool(meta.get("archived", False))
                if archived is not None and is_archived != archived:
                    continue
                if archived is None and is_archived and not include_archived:
                    continue
                
                # Fetch artifacts for this run
                artifacts = registry_store.get_run_artifacts(run.run_id)
                docx_artifact = next((a for a in artifacts if a.artifact_type == "docx"), None)
                pdf_artifact = next((a for a in artifacts if a.artifact_type == "pdf"), None)
                
                docx_name = docx_artifact.filename if docx_artifact else None
                pdf_name = pdf_artifact.filename if pdf_artifact else None
                
                # Filter out DOCX files that no longer exist on disk (matching legacy logic)
                if docx_name and not os.path.exists(os.path.join(output_dir, docx_name)):
                    if not os.path.exists(os.path.join(output_dir, run.run_id, docx_name)):
                        continue
                
                # Reconstruct legacy history item
                # Snapshot configs
                snapshots = registry_store.get_run_snapshots(run.run_id)
                runtime_template = None
                runtime_prompt_manifest = None
                
                for s in snapshots:
                    if s.snapshot_type == "runtime_template":
                        try:
                            runtime_template = json.loads(s.metadata_json)
                        except Exception:
                            pass
                    elif s.snapshot_type == "runtime_prompt_manifest":
                        try:
                            runtime_prompt_manifest = json.loads(s.metadata_json)
                        except Exception:
                            pass
                
                # Sources
                sources = registry_store.get_run_sources(run.run_id)
                continuation_source = None
                for src in sources:
                    if src.source_type == "continuation" and src.metadata_json:
                        try:
                            continuation_source = json.loads(src.metadata_json)
                        except Exception:
                            pass
                
                # Construct history metadata compatible payload
                legacy_file = meta.get("legacy_metadata_file")
                metadata_id = legacy_file if legacy_file else f"{run.run_id}.metadata.json"
                
                template_mode = meta.get("template_mode")
                template_id = meta.get("template_id")
                
                item = {
                    "id": metadata_id,
                    "run_id": run.run_id,
                    "filename": docx_name,
                    "pdf_filename": pdf_name,
                    "artifact_sizes": {
                        "docx": artifact_size(docx_artifact, docx_name, run.run_id),
                        "pdf": artifact_size(pdf_artifact, pdf_name, run.run_id),
                    },
                    "topic": run.topic or "Unknown",
                    "instructions": run.instructions_preview,
                    "previous_prompt": meta.get("previous_prompt"),
                    "timestamp": run.created_at,
                    "author": meta.get("author"),
                    "status": run.status.upper(),
                    "archived": is_archived,
                    "archived_at": meta.get("archived_at"),
                    "context": meta.get("context", {}),
                    "document_plan": meta.get("document_plan"),
                    "original_context": meta.get("original_context", {}),
                    "academic_mode": bool(meta.get("academic_mode", False)),
                    "logs": meta.get("logs", []),
                    "reviewer_feedback": meta.get("reviewer_feedback", []),
                    "export_report": meta.get("export_report"),
                    "template_mode": template_mode,
                    "template_id": template_id,
                    "runtime_template": runtime_template or meta.get("runtime_template"),
                    "runtime_prompt_manifest": runtime_prompt_manifest or meta.get("runtime_prompt_manifest"),
                    "resolved_manifest": meta.get("resolved_manifest"),
                    "resolved_contract": meta.get("resolved_contract"),
                    "contract_sexpr": meta.get("contract_sexpr"),
                    "manifest_selection": meta.get("manifest_selection"),
                    "decision_summary": meta.get("decision_summary"),
                    "continuation_source": continuation_source,
                    "artifact_override": meta.get("artifact_override"),
                    "continuation_intent": meta.get("continuation_intent"),
                    "document_state": meta.get("document_state"),
                    "edit_plan": meta.get("edit_plan"),
                    "merge_patch": meta.get("merge_patch"),
                }
                history.append(item)
                
            history.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            return history
            
        except Exception as e:
            logging.getLogger(__name__).warning("Failed to load history from SQLite Registry, falling back to legacy JSON: %s", e)

    output_dir = _pipeline_output_dir()
    metadata_dir = _history_metadata_dir()
        
    if not os.path.exists(metadata_dir):
        return []
        
    history = []
    for f in os.listdir(metadata_dir):
        if f.endswith(".metadata.json"):
            metadata_path = os.path.join(metadata_dir, f)
            try:
                with open(metadata_path, "r", encoding="utf-8") as file:
                    data = json.load(file)
                is_archived = bool(data.get("archived", False))
                if archived is not None and is_archived != archived:
                    continue
                if archived is None and is_archived and not include_archived:
                    continue
                docx_name = data.get("docx_filename")
                if not docx_name or os.path.exists(os.path.join(output_dir, docx_name)):
                    history.append(_history_item_from_metadata(f, data))
            except Exception as e:
                logging.getLogger(__name__).warning("Failed to load metadata file %s: %s", f, e)
                
    history.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return history


@app.post("/api/history/{metadata_id}/archive")
def archive_history_item(metadata_id: str):
    metadata_path, data = _load_history_metadata(metadata_id)
    data["archived"] = True
    data["archived_at"] = datetime.now().isoformat(timespec="seconds")
    _write_history_metadata(metadata_path, data)
    return _history_item_from_metadata(metadata_id, data)


@app.post("/api/history/{metadata_id}/unarchive")
def unarchive_history_item(metadata_id: str):
    metadata_path, data = _load_history_metadata(metadata_id)
    data["archived"] = False
    data["archived_at"] = None
    _write_history_metadata(metadata_path, data)
    return _history_item_from_metadata(metadata_id, data)


@app.post("/api/history/unarchive")
def bulk_unarchive_history_items(payload: BulkHistoryPayload):
    restored = []
    for metadata_id in payload.ids:
        metadata_path, data = _load_history_metadata(metadata_id)
        data["archived"] = False
        data["archived_at"] = None
        _write_history_metadata(metadata_path, data)
        restored.append(_history_item_from_metadata(metadata_id, data))
    return {"restored": restored}


@app.delete("/api/history/{metadata_id}")
def delete_history_item(metadata_id: str):
    if not metadata_id or metadata_id != os.path.basename(metadata_id):
        raise HTTPException(status_code=400, detail="Invalid history metadata id")
    if not metadata_id.endswith(".metadata.json"):
        raise HTTPException(status_code=400, detail="Invalid history metadata id")

    metadata_dir = os.path.abspath(_history_metadata_dir())
    metadata_path = os.path.abspath(os.path.join(metadata_dir, metadata_id))
    if not metadata_path.startswith(metadata_dir + os.sep):
        raise HTTPException(status_code=403, detail="Access denied")

    data = {}
    metadata_exists = os.path.exists(metadata_path)
    if metadata_exists:
        try:
            with open(metadata_path, "r", encoding="utf-8") as file:
                data = json.load(file)
        except json.JSONDecodeError:
            logging.getLogger(__name__).warning("Metadata file %s is invalid JSON", metadata_path)
        except Exception as e:
            logging.getLogger(__name__).warning("Failed to read metadata file %s: %s", metadata_path, e)

    if data.get("docx_filename"):
        try:
            _delete_export_asset(data.get("docx_filename"))
        except Exception as e:
            logging.getLogger(__name__).warning("Failed to delete docx asset: %s", e)
    if data.get("pdf_filename"):
        try:
            _delete_export_asset(data.get("pdf_filename"))
        except Exception as e:
            logging.getLogger(__name__).warning("Failed to delete pdf asset: %s", e)

    run_id = _resolve_history_run_id(metadata_id, data)
    if run_id:
        try:
            registry_store.delete_run(run_id)
        except Exception as e:
            logging.getLogger(__name__).warning("Failed to delete run from SQLite: %s", e)

    if metadata_id.startswith("run_"):
        run_id_for_dir = metadata_id.split(".")[0]
        _delete_run_directory(run_id_for_dir)

    if metadata_exists:
        try:
            os.remove(metadata_path)
        except Exception as e:
            logging.getLogger(__name__).warning("Failed to delete metadata file %s: %s", metadata_path, e)

    return {"status": "deleted", "id": metadata_id}


@app.post("/api/history/reset")
def hard_reset():
    # This is a legacy local-first maintenance operation. Service workspaces use
    # the authenticated, tenant-scoped cleanup API instead.
    if os.getenv("APE_DATABASE_SYNC_URL"):
        raise HTTPException(status_code=404, detail="history reset is unavailable in service mode")
    # 1. Clear database tables
    try:
        with registry_store._connection() as conn:
            conn.execute("PRAGMA foreign_keys = OFF;")
            conn.execute("DELETE FROM runs;")
            conn.execute("DELETE FROM run_agents;")
            conn.execute("DELETE FROM artifacts;")
            conn.execute("DELETE FROM runtime_snapshots;")
            conn.execute("DELETE FROM sections;")
            conn.execute("DELETE FROM sources;")
            conn.execute("DELETE FROM evaluations;")
            conn.execute("DELETE FROM events;")
            conn.execute("PRAGMA foreign_keys = ON;")
    except Exception as e:
        logging.getLogger(__name__).warning("Failed to clear SQLite tables: %s", e)

    # 2. Delete legacy metadata files (*.metadata.json) in exports/_metadata
    metadata_dir = _history_metadata_dir()
    if os.path.exists(metadata_dir):
        for f in os.listdir(metadata_dir):
            if f.endswith(".metadata.json"):
                try:
                    os.remove(os.path.join(metadata_dir, f))
                except Exception as e:
                    logging.getLogger(__name__).warning("Failed to remove metadata file %s: %s", f, e)

    # 3. Delete run directories (exports/run_*)
    exports_dir = "exports"
    if os.path.exists(exports_dir):
        import shutil
        import re
        for name in os.listdir(exports_dir):
            path = os.path.join(exports_dir, name)
            if os.path.isdir(path) and re.match(r"^run_\d{8}_\d{6}$", name):
                try:
                    shutil.rmtree(path)
                except Exception as e:
                    logging.getLogger(__name__).warning("Failed to remove run directory %s: %s", path, e)

    # 4. Clean up exported docx or pdf files in output dir
    output_dir = _pipeline_output_dir()
    if os.path.exists(output_dir):
        for name in os.listdir(output_dir):
            path = os.path.join(output_dir, name)
            if os.path.isfile(path) and (name.endswith(".docx") or name.endswith(".pdf")):
                try:
                    os.remove(path)
                except Exception as e:
                    logging.getLogger(__name__).warning("Failed to remove export file %s: %s", path, e)

    return {"status": "reset_completed"}


@app.get("/api/registry/runs")
def list_registry_runs(
    kind: Optional[str] = None,
    status: Optional[str] = None,
    pipeline_mode: Optional[str] = None,
    template_id: Optional[str] = None,
    artifact_type: Optional[str] = None,
    created_date: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    try:
        runs = registry_store.list_runs(
            kind=kind,
            status=status,
            pipeline_mode=pipeline_mode,
            template_id=template_id,
            artifact_type=artifact_type,
            created_date=created_date,
            limit=limit,
            offset=offset,
        )
        return [run.model_dump(mode="json") for run in runs]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query registry: {str(e)}")


@app.get("/api/registry/runs/{run_id}")
def inspect_registry_run(run_id: str):
    try:
        run = registry_store.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found in registry")
            
        agents = registry_store.get_run_agents(run_id)
        artifacts = registry_store.get_run_artifacts(run_id)
        snapshots = registry_store.get_run_snapshots(run_id)
        sections = registry_store.get_run_sections(run_id)
        sources = registry_store.get_run_sources(run_id)
        evaluations = registry_store.get_run_evaluations(run_id)
        events = registry_store.get_run_events(run_id)
        
        return {
            "run": run.model_dump(mode="json"),
            "agents": [x.model_dump(mode="json") for x in agents],
            "artifacts": [x.model_dump(mode="json") for x in artifacts],
            "snapshots": [x.model_dump(mode="json") for x in snapshots],
            "sections": [x.model_dump(mode="json") for x in sections],
            "sources": [x.model_dump(mode="json") for x in sources],
            "evaluations": [x.model_dump(mode="json") for x in evaluations],
            "events": [x.model_dump(mode="json") for x in events],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to inspect run {run_id}: {str(e)}")


# New Routes for Secrets and Models Manager
from academic_pe.core.secrets import is_secret_configured, save_secret, get_secret
from openai import OpenAI

@app.get("/api/secrets")
def get_secrets_status():
    providers = ["openai", "anthropic", "google", "custom_openai", "lm_studio", "zen"]
    return {p: get_secret(p) or "" for p in providers}

@app.post("/api/secrets")
def update_secret_endpoint(payload: SecretUpdatePayload):
    try:
        save_secret(payload.provider, payload.api_key)
        return {"status": "success", "message": f"API key for {payload.provider} saved successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save secret: {str(e)}")

@app.get("/api/models")
def get_provider_models(provider: str, base_url: Optional[str] = None):
    # Load API key dynamically
    api_key = get_secret(provider)
    
    if provider == "mock":
        return ["mock-model-1", "mock-model-2"]
        
    elif provider == "openai":
        return ["gpt-5.5", "gpt-5.4", "gpt-5.4-mini"]
            
    elif provider == "google":
        return ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-3.1-pro-preview"]
        
    elif provider == "anthropic":
        return ["Claude Opus 4.8", "Claude Sonnet 4.6", "Claude Haiku 4.5"]
        
    elif provider == "lm_studio":
        return []

    elif provider == "custom_openai":
        url = base_url
        if not url:
            return []
        try:
            client_key = api_key or "lm-studio"
            client = OpenAI(api_key=client_key, base_url=url)
            resp = client.models.list()
            return [m.id for m in resp.data]
        except Exception as e:
            logging.getLogger(__name__).warning("Custom OpenAI/LM Studio models list failed: %s", e)
            return []
    elif provider == "zen":
        return [
            "deepseek-v4-flash-free",
            "mimo-v2.5-free",
            "big-pickle",
            "nemotron-3-ultra-free",
            "north-mini-code-free",
        ]
            
    return []

@app.post("/api/context")
def update_context(payload: Dict[str, str]):
    global current_run
    with run_lock:
        current_run["context"] = payload
    return {"status": "success"}
