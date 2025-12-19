from enum import Enum, auto
from typing import Dict, Any, Optional
from src.core.config import load_config
from src.core.llm import LLMClient
from src.agents.base import BaseAgent
from src.tools.docx_renderer import render_paper

class PipelineState(Enum):
    INIT = auto()
    DRAFTING = auto()
    REVIEWING = auto()
    RENDERING = auto()
    DONE = auto()

class Orchestrator:
    def __init__(self, config_path: str = "config/agents.yaml"):
        self.config = load_config(config_path)
        self.llm = LLMClient()
        self.state = PipelineState.INIT
        self.context: Dict[str, str] = {}

        # Initialize Agents
        writer_cfg = self.config.agents.get('writer')
        reviewer_cfg = self.config.agents.get('reviewer')

        if not writer_cfg:
            raise ValueError("Writer agent configuration is missing")

        self.writer = BaseAgent(writer_cfg, self.llm)
        self.reviewer = BaseAgent(reviewer_cfg, self.llm) if reviewer_cfg else None

    def run_pipeline(self):
        """
        Executes the linear pipeline: Draft -> Review -> Render.
        """
        print(f"[{self.state.name}] Pipeline initialized.")

        # --- STATE: DRAFTING ---
        self.state = PipelineState.DRAFTING
        print(f"[{self.state.name}] Writer Agent starting tasks...")

        # 1. Draft Theory
        self.context['theory'] = self.writer.process(
            "Write a detailed Chapter 1 (Theory) about State Machines. Structure it with H2 and H3 headers."
        )

        # 2. Draft Calculation
        self.context['calculation'] = self.writer.process(
            "Write a Chapter 2 (Calculations) with LaTeX formulas illustrating algorithmic complexity ($O(n)$)."
        )

        # 3. Draft Conclusion
        self.context['conclusion'] = self.writer.process(
            "Write a Conclusion summarizing the efficiency of State Machines."
        )

        # --- STATE: REVIEWING ---
        self.state = PipelineState.REVIEWING
        print(f"[{self.state.name}] Reviewer Agent validating content...")

        if self.reviewer:
            # Demonstration of review loop (non-blocking in this MVP)
            critique = self.reviewer.process(
                "Check the provided text for academic tone and formatting errors. Return 'APPROVED' or a list of issues.",
                context=self.context['theory'][:1000] # Send first part for check
            )
            print(f"Reviewer Status: {critique[:50]}...")
        else:
            print("Reviewer not configured, skipping.")

        # --- STATE: RENDERING ---
        self.state = PipelineState.RENDERING
        print(f"[{self.state.name}] Sending content to Docx Renderer...")

        output_path = render_paper(self.context, output_filename="Final_Academic_Paper.docx")

        # --- STATE: DONE ---
        self.state = PipelineState.DONE
        print(f"[{self.state.name}] Workflow complete. Artifact: {output_path}")

        return output_path
