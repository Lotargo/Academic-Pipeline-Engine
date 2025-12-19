import yaml
from pydantic import BaseModel
from typing import Dict
import os

class AgentConfig(BaseModel):
    role: str
    model: str
    temperature: float
    system_prompt: str

class AppConfig(BaseModel):
    agents: Dict[str, AgentConfig]

def load_config(path: str = "config/agents.yaml") -> AppConfig:
    """
    Loads configuration from a YAML file and validates it with Pydantic.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Configuration file not found at {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return AppConfig(**data)
