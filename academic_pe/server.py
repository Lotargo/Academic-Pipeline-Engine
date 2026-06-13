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
from typing import Dict, List, Optional, Callable
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from academic_pe.api_models import BulkHistoryPayload, ConfigUpdateRequest, ExportRequest, RunRequest, SecretUpdatePayload, PromptEnhanceRequest, PromptEnhanceResponse
from academic_pe.core.config import TemplateMode, load_config, AppConfig
from academic_pe.core.orchestrator import create_orchestrator_from_config, PipelineState, PipelineCancelled
from academic_pe.core.template_library import TemplateLibrary
from academic_pe.tools.export_qa import export_docx_with_qa, export_pdf_with_qa
from academic_pe.tools.libreoffice import discover_soffice

_background_tasks = set()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Clean up empty run directories on startup
    cleanup_empty_run_directories()
    
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

# CORS middleware for Next.js on port 3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for exports directory to serve generated charts and other files
from fastapi.staticfiles import StaticFiles
os.makedirs("exports", exist_ok=True)
app.mount("/api/exports", StaticFiles(directory="exports"), name="exports")


# Global status tracking object
current_run = {
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
}


def _exportable_context(context: Dict[str, str]) -> Dict[str, str]:
    return {key: value for key, value in context.items() if key != "document_plan"}


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


def _history_item_from_metadata(metadata_id: str, data: dict) -> dict:
    run_id = _resolve_history_run_id(metadata_id, data)
    return {
        "id": metadata_id,
        "run_id": run_id,
        "filename": data.get("docx_filename"),
        "pdf_filename": data.get("pdf_filename"),
        "topic": data.get("topic", "Unknown"),
        "timestamp": data.get("timestamp", ""),
        "author": data.get("author"),
        "status": data.get("status", "COMPLETED"),
        "archived": bool(data.get("archived", False)),
        "archived_at": data.get("archived_at"),
        "context": data.get("context", {}),
        "original_context": data.get("original_context", {}),
        "academic_mode": data.get("academic_mode", False),
        "logs": data.get("logs", []),
        "reviewer_feedback": data.get("reviewer_feedback", []),
        "export_report": data.get("export_report"),
        "template_mode": data.get("template_mode"),
        "template_id": data.get("template_id"),
        "runtime_template": data.get("runtime_template"),
        "runtime_prompt_manifest": data.get("runtime_prompt_manifest"),
    }


def _delete_export_asset(docx_name: Optional[str]) -> None:
    if not docx_name:
        return

    output_dir = os.path.abspath(_pipeline_output_dir())
    file_path = os.path.abspath(os.path.join(output_dir, docx_name))
    if not file_path.startswith(output_dir + os.sep):
        raise HTTPException(status_code=403, detail="Export path is outside the output directory")
    if os.path.exists(file_path) and os.path.isfile(file_path):
        os.remove(file_path)

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
    try:
        from academic_pe.core.dynamic_examples import generate_new_examples, load_cached_examples
        await generate_new_examples()
        
        config = load_config("config/agents.yaml")
        lang = config.ui.language
        examples = await load_cached_examples(lang)
        from academic_pe.core.dynamic_examples import last_generated_at
        return {
            "examples": examples,
            "last_generated": last_generated_at * 1000,
            "ttl": max(getattr(config, "dynamic_examples_interval_mins", 15) * 60, 60),
            "dynamic": True
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/prompt/enhance", response_model=PromptEnhanceResponse)
async def enhance_prompt(payload: PromptEnhanceRequest):
    """
    Uses the example_generator agent to enhance a raw topic and instructions
    into a mathematically/technically deep academic research task.
    """
    import re
    from academic_pe.agents.factory import create_agent

    try:
        config = load_config("config/agents.yaml")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load configuration: {str(e)}")

    agent_cfg = config.agents.get("example_generator")
    if not agent_cfg:
        raise HTTPException(status_code=500, detail="example_generator agent configuration not found in agents.yaml")

    lang = config.ui.language

    # Build prompt manifest
    prompt = (
        f"You are a senior academic director and prompt engineer.\n"
        f"Your task is to refine and enrich the following raw, draft topic and instructions into a well-structured, professional task description, tailored exactly to the requested scope, field of study, complexity level, and target audience.\n"
        f"Generate the enhanced topic and instructions in the language corresponding to '{lang}' "
        f"(e.g., if 'ru' write in Russian, if 'en' write in English).\n\n"
        f"Raw Topic: {payload.topic}\n"
        f"Raw Guidelines/Instructions: {payload.instructions or ''}\n\n"
        f"Crucial Alignment Rules:\n"
        f"1. Preserve Specific Details: You MUST preserve and respect any specific constraints, facts, and parameters provided in the raw guidelines. This includes student/author names (e.g. 'Золотарёва Е.К.'), class/year ('9-Б класс'), school details ('СОШ №235, г. Москва'), specific structural elements (e.g., 'обязательно нужен титульник'), and avoiding AI-typical phrases ('главное не спалиться что это ии написал'). Do not drop or ignore these facts.\n"
        f"2. Dynamic Complexity & Domain Alignment: Adapt the instructions to the level and field of the paper:\n"
        f"   - For technical/scientific domains (physics, CS, engineering, mathematics), mandate LaTeX formulas, formal impersonal tone, and deep mathematical formulations.\n"
        f"   - For humanities, history, school essays, and general reports, focus instructions on historical context, chronological structure, source critique, and thematic coverage. Do NOT force advanced mathematical analysis (like statistical modeling, Poisson distribution, correlation/regression formulas, or $O(N \\log N)$ complexity) onto a non-mathematical or school-level task unless explicitly requested in the raw guidelines.\n"
        f"3. General Professional Guidelines: Mandate the use of structured headings (H2/H3 headers), consistent terminology, and a formal/appropriate tone. Explicitly forbid placeholders (e.g. [insert link]), AI meta-text, conversational filler, and obvious AI self-references.\n"
        f"4. Project Constraints & Digital Context: Since this is an automated document pipeline that drafts, reviews, and exports files to .docx, all instructions must be purely digital. Never generate physical-world instructions or tasks (such as 'распечатать реферат', 'сброшюровать', 'сдать лично', 'подписать вручную' / 'print the document', 'bind it', 'physically submit', 'hand-sign'). All guidelines must focus strictly on document content, structure, formatting, figures, tables, math, style, and citations.\n\n"
        f"Return ONLY a valid JSON object matching the schema below. Do not include markdown code block fences (```json ... ```), wrapper text, or explanations outside the JSON object.\n"
        f"Schema:\n"
        f"{{\n"
        f"  \"topic\": \"Enhanced, professionally formulated topic or title\",\n"
        f"  \"instructions\": \"Enriched, detailed guidelines and structure list for the writing pipeline\"\n"
        f"}}"
    )

    loop = asyncio.get_running_loop()

    def run_agent():
        agent = create_agent(
            "example_generator",
            agent_cfg,
            retry_cfg=config.retry,
            cb_cfg=config.circuit_breaker
        )
        return agent.process(prompt)

    try:
        raw_response = await loop.run_in_executor(None, run_agent)
        
        # Parse the JSON object
        text = raw_response.strip()
        if "```" in text:
            match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
            if match:
                text = match.group(1).strip()
                
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Fallback regex search for the first { to the last }
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                json_slice = text[start:end+1]
                data = json.loads(json_slice)
            else:
                raise ValueError("No JSON object structure found in the agent response")

        if not isinstance(data, dict) or "topic" not in data or "instructions" not in data:
            raise ValueError("Parsed JSON is not in the expected format (missing topic or instructions)")

        return PromptEnhanceResponse(
            topic=data["topic"].strip(),
            instructions=data["instructions"].strip()
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
        with run_lock:
            current_run["template_mode"] = config.pipeline.template_mode.value
            current_run["template_id"] = config.pipeline.template_id
            current_run["academic_mode"] = config.pipeline.academic_mode
            current_run["document_plan"] = None
        
        # Apply legacy section-topic overrides only for the current custom structure.
        # Fixed templates must remain structurally bound to the selected template.
        if topic and config.pipeline.template_mode == TemplateMode.custom:
            with run_lock:
                current_run["topic"] = topic
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
        metadata = {
            "topic": topic,
            "instructions": instructions,
            "author": author,
            "run_id": run_id,
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
            "original_context": current_run.get("original_context", {}),
            "academic_mode": config.pipeline.academic_mode,
            "logs": current_run["logs"],
            "reviewer_feedback": current_run["reviewer_feedback"]
        }
        with open(metadata_filename, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
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

    background_tasks.add_task(
        run_pipeline_thread,
        payload.topic,
        payload.instructions,
        payload.template_mode,
        payload.template_id,
        payload.academic_mode,
        run_id,
        payload.author,
    )
    return {"status": "started", "message": "Pipeline execution started in the background"}


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
            config = _apply_runtime_template(config, runtime_template)
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
    metadata_dir = os.path.join("exports", "_metadata")
    os.makedirs(metadata_dir, exist_ok=True)
    metadata_filename = os.path.join(
        metadata_dir,
        f"{Path(result.filename).stem}.{datetime.now().strftime('%Y%m%d%H%M%S')}.metadata.json",
    )
    metadata = {
        "topic": topic,
        "instructions": None,
        "author": author,
        "run_id": run_id,
        "template_mode": current_run.get("template_mode") or config.pipeline.template_mode.value,
        "template_id": current_run.get("template_id") or config.pipeline.template_id,
        "runtime_template": current_run.get("runtime_template"),
        "runtime_prompt_manifest": current_run.get("runtime_prompt_manifest"),
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
    }
    with open(metadata_filename, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)


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
                "Не удалось сохранить документ. Файл открыт в другой программе (например, Microsoft Word) "
                "и заблокирован. Пожалуйста, закройте его и попробуйте снова. / "
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
                # Include draft records and exported DOCX records.
                docx_name = data.get("docx_filename")
                if not docx_name or os.path.exists(os.path.join(output_dir, docx_name)):
                    history.append(_history_item_from_metadata(f, data))
            except Exception as e:
                logging.getLogger(__name__).warning("Failed to load metadata file %s: %s", f, e)
                
    # Sort by timestamp desc
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
    metadata_path, data = _load_history_metadata(metadata_id)
    _delete_export_asset(data.get("docx_filename"))
    _delete_export_asset(data.get("pdf_filename"))
    if metadata_id.startswith("run_"):
        run_id = metadata_id.split(".")[0]
        _delete_run_directory(run_id)
    os.remove(metadata_path)
    return {"status": "deleted", "id": metadata_id}

# New Routes for Secrets and Models Manager
from academic_pe.core.secrets import is_secret_configured, save_secret, get_secret
import requests  # type: ignore
from openai import OpenAI

@app.get("/api/secrets")
def get_secrets_status():
    providers = ["openai", "anthropic", "google", "custom_openai", "lm_studio", "zen"]
    return {p: is_secret_configured(p) for p in providers}

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
        if not api_key:
            return ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]
        try:
            client = OpenAI(api_key=api_key)
            resp = client.models.list()
            chat_models = [m.id for m in resp.data if any(x in m.id for x in ["gpt-4", "gpt-3.5", "o1", "o3", "chatgpt"])]
            return chat_models if chat_models else [m.id for m in resp.data]
        except Exception as e:
            logging.getLogger(__name__).warning("OpenAI models list failed: %s", e)
            return ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]
            
    elif provider == "google":
        if not api_key:
            return ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash", "gemini-1.5-pro"]
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                data = r.json()
                models = []
                for m in data.get("models", []):
                    name = m.get("name", "")
                    if name.startswith("models/"):
                        name = name[7:]
                    if "gemini" in name:
                        models.append(name)
                return models if models else ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash", "gemini-1.5-pro"]
        except Exception as e:
            logging.getLogger(__name__).warning("Google models list failed: %s", e)
        return ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash", "gemini-1.5-pro"]
        
    elif provider == "anthropic":
        if not api_key:
            return ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"]
        try:
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            }
            r = requests.get("https://api.anthropic.com/v1/models", headers=headers, timeout=5)
            if r.status_code == 200:
                data = r.json()
                return [m["id"] for m in data.get("data", [])]
        except Exception as e:
            logging.getLogger(__name__).warning("Anthropic models list failed: %s", e)
        return ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"]
        
    elif provider in ["custom_openai", "lm_studio"]:
        url = base_url
        if not url:
            url = "http://localhost:1234/v1" if provider == "lm_studio" else None
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
        if not api_key:
            return ["gpt-4o", "claude-3-5-sonnet", "gemini-1.5-pro", "deepseek-coder"]
        try:
            client = OpenAI(api_key=api_key, base_url="https://opencode.ai/zen/v1")
            resp = client.models.list()
            return [m.id for m in resp.data]
        except Exception as e:
            logging.getLogger(__name__).warning("OpenCode Zen models list failed: %s", e)
            return ["gpt-4o", "claude-3-5-sonnet", "gemini-1.5-pro", "deepseek-coder"]
            
    return []

@app.post("/api/context")
def update_context(payload: Dict[str, str]):
    global current_run
    with run_lock:
        current_run["context"] = payload
    return {"status": "success"}
