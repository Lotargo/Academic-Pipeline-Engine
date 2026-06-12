import os
import json
import yaml
import logging
import threading
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from academic_pe.core.config import load_config, AppConfig
from academic_pe.core.orchestrator import create_orchestrator, PipelineState, PipelineCancelled
from academic_pe.tools.export_qa import export_docx_with_qa
from academic_pe.tools.libreoffice import discover_soffice

# Create FastAPI app
app = FastAPI(title="Academic PE API Server", version="0.1.0")

# CORS middleware for Next.js on port 3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global status tracking object
current_run = {
    "status": "IDLE",  # IDLE, RUNNING, COMPLETED, FAILED
    "state": "INIT",
    "logs": [],
    "context": {},
    "reviewer_feedback": [],
    "docx_filename": None,
    "export_report": None,
    "error": None,
    "topic": "",
    "timestamp": None,
    "active_section": None,
}

# Thread lock for safety
run_lock = threading.Lock()

# Current orchestrator instance for cancellation
_current_orchestrator = None
_orchestrator_lock = threading.Lock()


def _pipeline_output_dir() -> str:
    try:
        config = load_config("config/agents.yaml")
        return config.pipeline.output_dir
    except Exception:
        return "exports"


def _metadata_dir(output_dir: str) -> str:
    return os.path.join(output_dir, "_metadata")

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

# Request Models
class RunRequest(BaseModel):
    topic: str
    instructions: Optional[str] = None

class ConfigUpdateRequest(BaseModel):
    config: dict


class ExportRequest(BaseModel):
    filename: Optional[str] = None
    topic: Optional[str] = None
    context: Optional[Dict[str, str]] = None

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

def run_pipeline_thread(topic: str, instructions: Optional[str]):
    global current_run, _current_orchestrator
    
    # Configure logging capturing
    status_handler = StatusLogHandler(current_run["logs"])
    root_logger.addHandler(status_handler)
    
    try:
        # Load local configuration
        config = load_config("config/agents.yaml")
        
        # Apply prompt overrides if topic is provided
        if topic:
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
        orch = create_orchestrator(config_path="config/agents.yaml")
        
        # Store orchestrator for cancellation
        with _orchestrator_lock:
            _current_orchestrator = orch
        
        # Synchronize config references to apply topic changes
        orch._config = config
        orch.user_topic = topic or ""
        orch.user_instructions = instructions or ""
        
        # Intercept context modifications to update current_run safely in real time
        def on_context_change(d):
            with run_lock:
                current_run["context"] = dict(d)

        def on_section_delta(section_name: str, delta: str, accumulated: str):
            with run_lock:
                context = dict(current_run.get("context") or {})
                context[section_name] = accumulated
                current_run["context"] = context
                current_run["active_section"] = section_name
        orch.context = InterceptingDict(on_context_change)
        
        # Set transition hooks
        def on_enter_hook(old_state, new_state):
            with run_lock:
                current_run["state"] = new_state.name
                current_run["logs"].append(f"[FSM] Entering state: {new_state.name}")
            
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
            def logged_reviewer_process(task_description: str, context: Optional[str] = None) -> str:
                res = orig_process(task_description, context)
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
        output_dir = os.path.dirname(output_path) if output_path else _pipeline_output_dir()
        metadata_dir = _metadata_dir(output_dir)
        os.makedirs(metadata_dir, exist_ok=True)
        metadata_filename = os.path.join(
            metadata_dir,
            f"{Path(output_path).stem}.{datetime.now().strftime('%Y%m%d%H%M%S')}.metadata.json",
        )
        metadata = {
            "topic": topic,
            "instructions": instructions,
            "timestamp": current_run["timestamp"],
            "status": "COMPLETED",
            "docx_filename": os.path.basename(output_path) if output_path else None,
            "context": orch.context,
            "logs": current_run["logs"],
            "reviewer_feedback": current_run["reviewer_feedback"]
        }
        with open(metadata_filename, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
            
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
        with _orchestrator_lock:
            _current_orchestrator = None
        root_logger.removeHandler(status_handler)

@app.post("/api/run")
def run_pipeline(payload: RunRequest, background_tasks: BackgroundTasks):
    global current_run
    
    with run_lock:
        if current_run["status"] == "RUNNING":
            raise HTTPException(status_code=400, detail="A pipeline is already executing")
            
        # Reset current run status
        current_run["status"] = "RUNNING"
        current_run["state"] = "INIT"
        current_run["logs"] = [f"Pipeline run triggered at {datetime.now().isoformat()}"]
        current_run["context"] = {}
        current_run["reviewer_feedback"] = []
        current_run["docx_filename"] = None
        current_run["export_report"] = None
        current_run["error"] = None
        current_run["topic"] = payload.topic
        current_run["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        current_run["active_section"] = None

    background_tasks.add_task(run_pipeline_thread, payload.topic, payload.instructions)
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


@app.post("/api/export/docx")
def export_docx(payload: ExportRequest):
    global current_run
    if payload.context:
        context = dict(payload.context)
        topic = payload.topic or "Untitled"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    else:
        with run_lock:
            if current_run["status"] == "RUNNING":
                raise HTTPException(status_code=400, detail="Cannot export while generation is still running")
            context = dict(current_run.get("context") or {})
            topic = current_run.get("topic") or "Untitled"
            timestamp = current_run.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with run_lock:
        if not payload.context and current_run["status"] == "RUNNING":
            raise HTTPException(status_code=400, detail="Cannot export while generation is still running")

    if not context:
        raise HTTPException(status_code=400, detail="No draft content is available to export")

    config = load_config("config/agents.yaml")
    result = export_docx_with_qa(context, config, output_filename=payload.filename)

    with run_lock:
        if not payload.context:
            current_run["docx_filename"] = result.filename
            current_run["export_report"] = result.to_dict()
        current_run["logs"].append(f"[Export QA]: {result.status.upper()} for {result.filename}")

    metadata_dir = _metadata_dir(config.pipeline.output_dir)
    os.makedirs(metadata_dir, exist_ok=True)
    metadata_filename = os.path.join(
        metadata_dir,
        f"{Path(result.filename).stem}.{datetime.now().strftime('%Y%m%d%H%M%S')}.metadata.json",
    )
    metadata = {
        "topic": topic,
        "instructions": None,
        "timestamp": timestamp,
        "status": "COMPLETED",
        "docx_filename": result.filename,
        "context": context,
        "logs": current_run.get("logs", []),
        "reviewer_feedback": current_run.get("reviewer_feedback", []),
        "export_report": result.to_dict(),
    }
    with open(metadata_filename, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    return result.to_dict()

@app.get("/api/download/{filename}")
def download_file(filename: str):
    output_dir = _pipeline_output_dir()
        
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(output_dir, safe_filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File {safe_filename} not found")
    return FileResponse(file_path, filename=safe_filename, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

@app.get("/api/history")
def get_history():
    output_dir = _pipeline_output_dir()
    metadata_dir = _metadata_dir(output_dir)
        
    if not os.path.exists(metadata_dir):
        return []
        
    history = []
    for f in os.listdir(metadata_dir):
        if f.endswith(".metadata.json"):
            metadata_path = os.path.join(metadata_dir, f)
            try:
                with open(metadata_path, "r", encoding="utf-8") as file:
                    data = json.load(file)
                # Include draft records and exported DOCX records.
                docx_name = data.get("docx_filename")
                if not docx_name or os.path.exists(os.path.join(output_dir, docx_name)):
                    history.append({
                        "filename": docx_name,
                        "topic": data.get("topic", "Unknown"),
                        "timestamp": data.get("timestamp", ""),
                        "status": data.get("status", "COMPLETED"),
                        "context": data.get("context", {}),
                        "logs": data.get("logs", []),
                        "reviewer_feedback": data.get("reviewer_feedback", []),
                        "export_report": data.get("export_report"),
                    })
            except Exception as e:
                logging.getLogger(__name__).warning("Failed to load metadata file %s: %s", f, e)
                
    # Sort by timestamp desc
    history.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return history

# New Routes for Secrets and Models Manager
from academic_pe.core.secrets import is_secret_configured, save_secret, get_secret
import requests  # type: ignore
from openai import OpenAI

class SecretUpdatePayload(BaseModel):
    provider: str
    api_key: str

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
