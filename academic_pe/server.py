import os
import json
import yaml
import logging
import threading
from datetime import datetime
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from academic_pe.core.config import load_config, AppConfig
from academic_pe.core.orchestrator import create_orchestrator, PipelineState
from academic_pe.tools.docx_renderer import render_paper

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
    "error": None,
    "topic": "",
    "timestamp": None
}

# Thread lock for safety
run_lock = threading.Lock()

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

def run_pipeline_thread(topic: str, instructions: Optional[str]):
    global current_run
    
    # Configure logging capturing
    status_handler = StatusLogHandler(current_run["logs"])
    root_logger.addHandler(status_handler)
    
    try:
        # Load local configuration
        config = load_config("config/agents.yaml")
        
        # Apply prompt overrides if topic is provided
        if topic:
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

        # Initialize orchestrator
        # We pass the render_paper directly to render
        orch = create_orchestrator(config_path="config/agents.yaml", renderer=render_paper)
        
        # Synchronize config references to apply topic changes
        orch._config = config
        
        # Set transition hooks
        def on_enter_hook(old_state, new_state):
            current_run["state"] = new_state.name
            current_run["logs"].append(f"[FSM] Entering state: {new_state.name}")
            
        def on_exit_hook(old_state, new_state):
            current_run["logs"].append(f"[FSM] Exiting state: {old_state.name}")
            
        orch.on_enter(on_enter_hook)
        orch.on_exit(on_exit_hook)
        
        # Intercept review decisions for progress logs
        orig_reviewer_process = None
        if orch._reviewer:
            orig_process = orch._reviewer.process
            def logged_reviewer_process(task_desc, context=None):
                res = orig_process(task_desc, context)
                current_run["reviewer_feedback"].append(res)
                current_run["logs"].append(f"[Reviewer Feedback]: {res}")
                return res
            orch._reviewer.process = logged_reviewer_process

        # Run pipeline
        output_path = orch.run_pipeline()
        
        # Update current context preview
        current_run["context"] = orch.context
        current_run["docx_filename"] = os.path.basename(output_path)
        current_run["status"] = "COMPLETED"
        current_run["state"] = "DONE"
        
        # Save history metadata
        metadata_filename = f"{os.path.splitext(output_path)[0]}.metadata.json"
        metadata = {
            "topic": topic,
            "instructions": instructions,
            "timestamp": current_run["timestamp"],
            "status": "COMPLETED",
            "docx_filename": os.path.basename(output_path),
            "context": orch.context,
            "logs": current_run["logs"],
            "reviewer_feedback": current_run["reviewer_feedback"]
        }
        with open(metadata_filename, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        current_run["status"] = "FAILED"
        current_run["state"] = "FAILED"
        current_run["error"] = str(e)
        current_run["logs"].append(f"[Error]: {str(e)}")
        logging.getLogger(__name__).exception("Pipeline background execution failed")
    finally:
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
        current_run["error"] = None
        current_run["topic"] = payload.topic
        current_run["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    background_tasks.add_task(run_pipeline_thread, payload.topic, payload.instructions)
    return {"status": "started", "message": "Pipeline execution started in the background"}

@app.get("/api/download/{filename}")
def download_file(filename: str):
    # Determine directory
    try:
        config = load_config("config/agents.yaml")
        output_dir = config.pipeline.output_dir
    except Exception:
        output_dir = "."
        
    file_path = os.path.join(output_dir, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File {filename} not found")
    return FileResponse(file_path, filename=filename, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

@app.get("/api/history")
def get_history():
    try:
        config = load_config("config/agents.yaml")
        output_dir = config.pipeline.output_dir
    except Exception:
        output_dir = "."
        
    if not os.path.exists(output_dir):
        return []
        
    history = []
    for f in os.listdir(output_dir):
        if f.endswith(".metadata.json"):
            metadata_path = os.path.join(output_dir, f)
            try:
                with open(metadata_path, "r", encoding="utf-8") as file:
                    data = json.load(file)
                # Verify that the associated docx exists
                docx_name = data.get("docx_filename")
                if docx_name and os.path.exists(os.path.join(output_dir, docx_name)):
                    history.append({
                        "filename": docx_name,
                        "topic": data.get("topic", "Unknown"),
                        "timestamp": data.get("timestamp", ""),
                        "status": data.get("status", "COMPLETED"),
                        "context": data.get("context", {}),
                        "logs": data.get("logs", []),
                        "reviewer_feedback": data.get("reviewer_feedback", [])
                    })
            except Exception as e:
                logging.getLogger(__name__).warning("Failed to load metadata file %s: %s", f, e)
                
    # Sort by timestamp desc
    history.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return history
