import yaml
from pydantic import BaseModel, Field
from typing import Dict, List
import os


class AgentConfig(BaseModel):
    role: str
    model: str
    temperature: float = Field(ge=0.0, le=2.0)
    system_prompt: str
    provider: str = "mock"
    base_url: str | None = None


class SectionPrompt(BaseModel):
    name: str
    topic: str
    instruction: str


class RetryConfig(BaseModel):
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0


class VolumeGateConfig(BaseModel):
    enabled: bool = True
    min_chars: int = 200


class LatexGateConfig(BaseModel):
    enabled: bool = True


class QualityGateConfig(BaseModel):
    volume: VolumeGateConfig = VolumeGateConfig()
    latex: LatexGateConfig = LatexGateConfig()


class PipelineConfig(BaseModel):
    sections: List[SectionPrompt]


class AppConfig(BaseModel):
    agents: Dict[str, AgentConfig]
    retry: RetryConfig = RetryConfig()
    quality_gate: QualityGateConfig = QualityGateConfig()
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
