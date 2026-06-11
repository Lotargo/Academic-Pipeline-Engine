import yaml
from pydantic import BaseModel, Field
from typing import Dict, List
import os


class AgentConfig(BaseModel):
    role: str
    model: str
    temperature: float = Field(ge=0.0, le=2.0)
    system_prompt: str


class SectionPrompt(BaseModel):
    name: str
    topic: str
    instruction: str


class PipelineConfig(BaseModel):
    sections: List[SectionPrompt]


class AppConfig(BaseModel):
    agents: Dict[str, AgentConfig]
    pipeline: PipelineConfig = PipelineConfig(sections=[
        SectionPrompt(name="theory", topic="State Machines",
                      instruction="Structure it with H2 and H3 headers."),
        SectionPrompt(name="calculation", topic="Algorithmic Complexity",
                      instruction="Include LaTeX formulas (e.g. $O(n)$)."),
        SectionPrompt(name="conclusion", topic="Efficiency of State Machines",
                      instruction="Summarize key findings and implications."),
    ])


def load_config(path: str = "config/agents.yaml") -> AppConfig:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Configuration file not found at {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return AppConfig(**data)
