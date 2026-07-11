import yaml
from enum import Enum
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
import os

from academic_pe.core.document_structure import HeadingPolicy, SemanticRole


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(override=False)
    except ImportError:
        pass


_load_dotenv()


class ProviderEnum(str, Enum):
    openai = "openai"
    custom_openai = "custom_openai"
    anthropic = "anthropic"
    google = "google"
    lm_studio = "lm_studio"
    zen = "zen"
    mock = "mock"


class ReasoningEffort(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    max = "max"


class LanguagePolicy(str, Enum):
    auto = "auto"
    en = "en"
    ru = "ru"
    zh = "zh"


class TemplateMode(str, Enum):
    fixed = "fixed"
    custom = "custom"
    auto = "auto"


class SelfCritiqueConfig(BaseModel):
    enabled: bool = False
    temperature: Optional[float] = None


class AgentConfig(BaseModel):
    role: str
    model: str = Field(..., min_length=1)
    temperature: float = Field(ge=0.0, le=2.0)
    reasoning_effort: Optional[ReasoningEffort] = None
    system_prompt: str
    provider: ProviderEnum = ProviderEnum.mock
    base_url: Optional[str] = None
    agent_type: Optional[str] = None
    self_critique: SelfCritiqueConfig = Field(default_factory=SelfCritiqueConfig)


class SectionPrompt(BaseModel):
    name: str
    topic: str
    instruction: str
    semantic_role: str = SemanticRole.body.value
    heading_policy: str = HeadingPolicy.render_required.value


class RetryConfig(BaseModel):
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0


class CircuitBreakerConfig(BaseModel):
    enabled: bool = False
    failure_threshold: int = 5
    recovery_timeout: float = 30.0


class VolumeGateConfig(BaseModel):
    enabled: bool = True
    min_chars: int = 200


class LatexGateConfig(BaseModel):
    enabled: bool = True


class MarkdownGateConfig(BaseModel):
    enabled: bool = True


class UnicodeHygieneGateConfig(BaseModel):
    enabled: bool = True


class PromptLeakageGateConfig(BaseModel):
    enabled: bool = True


class EvidenceGateConfig(BaseModel):
    enabled: bool = True
    require_ledger_urls: bool = True


class CalculationGateConfig(BaseModel):
    enabled: bool = True
    tolerance: float = Field(default=1e-6, ge=0.0)


class QualityGateConfig(BaseModel):
    volume: VolumeGateConfig = VolumeGateConfig()
    latex: LatexGateConfig = LatexGateConfig()
    markdown: MarkdownGateConfig = MarkdownGateConfig()
    unicode_hygiene: UnicodeHygieneGateConfig = UnicodeHygieneGateConfig()
    prompt_leakage: PromptLeakageGateConfig = PromptLeakageGateConfig()
    evidence: EvidenceGateConfig = EvidenceGateConfig()
    calculation: CalculationGateConfig = CalculationGateConfig()


class ExportQAConfig(BaseModel):
    enabled: bool = True
    auto_repair_enabled: bool = False
    warnings_log_enabled: bool = True
    provider: ProviderEnum = ProviderEnum.zen
    model: str = "mimo-v2.5-free"
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)


class TransitionConfig(BaseModel):
    from_state: str
    to_states: List[str]


class FSMConfig(BaseModel):
    enabled: bool = False
    states: List[str] = Field(default_factory=lambda: [
        "INIT", "PLANNING", "DRAFTING", "ASSEMBLING", "VALIDATING", "REVIEWING", "RENDERING", "DONE", "FAILED",
    ])
    transitions: List[TransitionConfig] = Field(default_factory=lambda: [
        TransitionConfig(from_state="INIT", to_states=["PLANNING", "DRAFTING"]),
        TransitionConfig(from_state="PLANNING", to_states=["DRAFTING"]),
        TransitionConfig(from_state="DRAFTING", to_states=["ASSEMBLING", "REVIEWING"]),
        TransitionConfig(from_state="ASSEMBLING", to_states=["VALIDATING"]),
        TransitionConfig(from_state="VALIDATING", to_states=["REVIEWING"]),
        TransitionConfig(from_state="REVIEWING", to_states=["DRAFTING", "RENDERING"]),
        TransitionConfig(from_state="RENDERING", to_states=["DONE"]),
        TransitionConfig(from_state="DONE", to_states=[]),
        TransitionConfig(from_state="FAILED", to_states=[]),
    ])


class StyleConfig(BaseModel):
    font_name: str = "Times New Roman"
    font_size: int = 14
    title_font_size: int = 20
    line_spacing: float = 1.5
    first_line_indent_cm: float = 1.25
    alignment: str = "justify"


class UIConfig(BaseModel):
    language: str = "ru"


class PipelineConfig(BaseModel):
    sections: List[SectionPrompt]
    output_filename: str = "Final_Academic_Paper.docx"
    output_dir: str = "exports"
    title: str = "GENERATED ACADEMIC PAPER"
    language: LanguagePolicy = LanguagePolicy.auto
    template_mode: TemplateMode = TemplateMode.custom
    template_id: Optional[str] = None
    academic_mode: bool = False


class AppConfig(BaseModel):
    agents: Dict[str, AgentConfig]
    retry: RetryConfig = RetryConfig()
    circuit_breaker: CircuitBreakerConfig = CircuitBreakerConfig()
    quality_gate: QualityGateConfig = QualityGateConfig()
    export_qa: ExportQAConfig = ExportQAConfig()
    fsm: FSMConfig = FSMConfig()
    style: StyleConfig = StyleConfig()
    ui: UIConfig = UIConfig()
    pipeline: PipelineConfig = PipelineConfig(sections=[
        SectionPrompt(name="theory", topic="State Machines",
                      instruction="Structure it with H2 and H3 headers."),
        SectionPrompt(name="calculation", topic="Algorithmic Complexity",
                      instruction="Include LaTeX formulas (e.g. $O(n)$)."),
        SectionPrompt(name="conclusion", topic="Efficiency of State Machines",
                      instruction="Summarize key findings and implications."),
    ])
    dynamic_examples_enabled: bool = True
    dynamic_examples_interval_mins: int = 15
    ocr_token_limit: int = 20000


_CONFIG_CACHE: Dict[str, AppConfig] = {}


def load_config(path: str = "config/agents.yaml") -> AppConfig:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Configuration file not found at {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        data = {}

    if "dynamic_examples_enabled" not in data:
        data["dynamic_examples_enabled"] = True

    if "dynamic_examples_interval_mins" not in data:
        data["dynamic_examples_interval_mins"] = 15

    if "export_qa" not in data:
        data["export_qa"] = {}

    if "agents" not in data:
        data["agents"] = {}

    if "planner" not in data["agents"]:
        data["agents"]["planner"] = {
            "role": "Planner",
            "provider": "zen",
            "model": "mimo-v2.5-free",
            "temperature": 0.2,
            "system_prompt": (
                "You are a professional artifact-aware template planner. Plan only the runtime "
                "artifact structure and prompt manifest. Do not draft artifact content."
            )
        }

    if "example_generator" not in data["agents"]:
        data["agents"]["example_generator"] = {
            "role": "Example Generator",
            "provider": "zen",
            "model": "deepseek-v4-flash-free",
            "temperature": 0.8,
            "system_prompt": (
                "You are an artifact-aware prompt helper. Generate 3 creative, diverse, and relevant artifact requests "
                "along with clear instructions for each, tailored to the requested interface language. "
                "Return ONLY a valid JSON array of objects without markdown code block syntax: "
                '[{"topic": "Topic Name", "instructions": "Guideline text"}]'
            )
        }

    if "brief_normalizer" not in data["agents"]:
        data["agents"]["brief_normalizer"] = {
            "role": "BriefNormalizer",
            "provider": "zen",
            "model": "mimo-v2.5-free",
            "temperature": 0.1,
            "agent_type": "brief_normalizer",
            "system_prompt": (
                "Extract a strict NormalizedBrief from the supplied task. Preserve explicit user intent, "
                "record ambiguity, and never design downstream prompts or document structure."
            ),
        }

    config = AppConfig(**data)
    _CONFIG_CACHE[path] = config
    return config


def get_cached_config(path: str = "config/agents.yaml") -> Optional[AppConfig]:
    return _CONFIG_CACHE.get(path)
