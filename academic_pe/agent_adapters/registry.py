from typing import Callable, Optional

from academic_pe.agent_adapters import exporter, planner, researcher, reviewer, writer


_GUIDANCE_BY_AGENT: dict[str, Callable[[Optional[str]], str]] = {
    "planner": planner.contract_guidance,
    "writer": writer.contract_guidance,
    "reviewer": reviewer.contract_guidance,
    "researcher": researcher.contract_guidance,
    "exporter": exporter.contract_guidance,
}


def contract_guidance_for_agent(agent_name: str, artifact_id: Optional[str] = None) -> str:
    guidance_factory = _GUIDANCE_BY_AGENT.get(agent_name)
    if guidance_factory is None:
        return "Agent: perform your role without changing the contract's artifact intent."
    return guidance_factory(artifact_id)
