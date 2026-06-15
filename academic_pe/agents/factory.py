from typing import Dict, Optional, Type

from academic_pe.agents.base import BaseAgent, DefaultAgent
from academic_pe.agents.researcher import ResearcherAgent
from academic_pe.agents.writer import WriterAgent, ReviewerAgent
from academic_pe.agents.prompt_enhancer import PromptEnhancerAgent
from academic_pe.core.config import AppConfig, AgentConfig, RetryConfig, CircuitBreakerConfig
from academic_pe.core.llm import create_provider, RetryConfig as LLMRetryConfig, CircuitBreakerConfig as LLMCBConfig

_AGENT_TYPES: Dict[str, Type[BaseAgent]] = {
    "default": DefaultAgent,
    "writer": WriterAgent,
    "reviewer": ReviewerAgent,
    "prompt_enhancer": PromptEnhancerAgent,
    "researcher": ResearcherAgent,
}


def register_agent_type(name: str, cls: Type[BaseAgent]) -> None:
    _AGENT_TYPES[name] = cls


def _build_llm(
    cfg: AgentConfig,
    retry_cfg: Optional[RetryConfig] = None,
    cb_cfg: Optional[CircuitBreakerConfig] = None,
):
    rc = None
    if retry_cfg is not None and retry_cfg.max_retries > 0:
        rc = LLMRetryConfig(
            max_retries=retry_cfg.max_retries,
            base_delay=retry_cfg.base_delay,
            max_delay=retry_cfg.max_delay,
        )

    cbc = None
    if cb_cfg is not None and cb_cfg.enabled:
        cbc = LLMCBConfig(
            failure_threshold=cb_cfg.failure_threshold,
            recovery_timeout=cb_cfg.recovery_timeout,
        )

    return create_provider(
        provider=cfg.provider.value,
        base_url=cfg.base_url,
        retry_config=rc,
        circuit_breaker_config=cbc,
    )


def create_agent(
    name: str,
    cfg: AgentConfig,
    retry_cfg: Optional[RetryConfig] = None,
    cb_cfg: Optional[CircuitBreakerConfig] = None,
    agent_type: Optional[str] = None,
) -> BaseAgent:
    if agent_type is None:
        agent_type = cfg.agent_type or (name if name in _AGENT_TYPES else "default")

    cls = _AGENT_TYPES.get(agent_type)
    if cls is None:
        raise ValueError(f"Unknown agent type: {agent_type}. Registered: {list(_AGENT_TYPES)}")

    llm = _build_llm(cfg, retry_cfg, cb_cfg)
    return cls(cfg, llm)


def create_agents(config: AppConfig) -> Dict[str, BaseAgent]:
    agents: Dict[str, BaseAgent] = {}
    for name, cfg in config.agents.items():
        agents[name] = create_agent(
            name, cfg,
            retry_cfg=config.retry,
            cb_cfg=config.circuit_breaker,
        )
    return agents
