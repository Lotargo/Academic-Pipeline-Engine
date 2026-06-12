import os
import pytest
from academic_pe.core.sandbox import (
    SandboxExecutionError,
    execute_sandbox_blocks,
    run_code_in_sandbox,
)
from academic_pe.core.orchestrator import Orchestrator, PipelineState, PipelineError
from academic_pe.core.config import AppConfig, AgentConfig, PipelineConfig, QualityGateConfig, VolumeGateConfig, LatexGateConfig, SectionPrompt
from academic_pe.core.llm import MockProvider
from academic_pe.agents.base import DefaultAgent


def test_run_code_success():
    res = run_code_in_sandbox("print('hello sandbox')")
    assert res.success is True
    assert res.stdout.strip() == "hello sandbox"
    assert res.stderr == ""
    assert res.exit_code == 0


def test_run_code_numpy():
    res = run_code_in_sandbox("import numpy as np; x = np.array([1, 2, 3]); print(x.mean())")
    assert res.success is True
    assert res.stdout.strip() == "2.0"


def test_run_code_sympy():
    res = run_code_in_sandbox("import sympy as sp; x = sp.Symbol('x'); print(sp.latex(x**2))")
    assert res.success is True
    assert res.stdout.strip() == "x^{2}"


def test_run_code_matplotlib():
    img_path = "exports/test_sandbox_plot.png"
    if os.path.exists(img_path):
        os.remove(img_path)

    os.makedirs("exports", exist_ok=True)
    code = f"""
import matplotlib.pyplot as plt
plt.plot([1, 2], [3, 4])
plt.savefig('{img_path}')
"""
    res = run_code_in_sandbox(code)
    assert res.success is True
    assert os.path.exists(img_path)
    os.remove(img_path)


def test_run_code_error_traceback():
    res = run_code_in_sandbox("1 / 0")
    assert res.success is False
    assert "ZeroDivisionError" in res.stderr
    assert res.exit_code != 0


def test_run_code_timeout():
    # Timeout after 1 second for test efficiency
    res = run_code_in_sandbox("import time; time.sleep(5)", timeout_seconds=1)
    assert res.success is False
    assert res.exit_code == -1
    # Check that it returns timeout or expired in some form
    assert "TimeoutExpired" in res.stderr


def test_execute_sandbox_blocks_success():
    text = """
Before
```python-run
print("Inside 1")
```
Middle
```python-run
print("Inside 2")
```
After
"""
    expected = """
Before
Inside 1
Middle
Inside 2
After
"""
    assert execute_sandbox_blocks(text) == expected


def test_execute_sandbox_blocks_failure():
    text = """
Before
```python-run
raise ValueError("oops")
```
"""
    with pytest.raises(SandboxExecutionError) as exc:
        execute_sandbox_blocks(text)
    assert "raise ValueError" in exc.value.code
    assert "ValueError: oops" in exc.value.stderr


def test_orchestrator_integration_academic_mode():
    class SandboxMockProvider(MockProvider):
        def generate(self, system_prompt, user_prompt, model, temperature, on_delta=None):
            if "Write a section" in user_prompt:
                return """
Here is my calculation:
```python-run
import numpy as np
print(np.sum([10, 20]))
```
"""
            return "APPROVED"

    config = AppConfig(
        agents={
            "writer": AgentConfig(
                role="Writer", model="mock", temperature=0.0,
                system_prompt="Writer prompt.",
            ),
        },
        pipeline=PipelineConfig(
            sections=[
                SectionPrompt(name="theory", topic="Theory", instruction="Explain."),
            ],
            academic_mode=True, # Enable academic mode!
        ),
        quality_gate=QualityGateConfig(
            volume=VolumeGateConfig(enabled=False),
            latex=LatexGateConfig(enabled=False),
        ),
    )

    llm = SandboxMockProvider()
    writer = DefaultAgent(config.agents["writer"], llm)
    orch = Orchestrator(writer=writer, config=config)

    result = orch.run_pipeline(render_artifact=False)
    assert orch.state == PipelineState.DONE
    # The final drafted content in the context must be evaluated
    assert "theory" in orch.context
    assert "30" in orch.context["theory"]
    assert "python-run" not in orch.context["theory"]


def test_orchestrator_integration_self_correction():
    calls = []

    class SelfCorrectionMockProvider(MockProvider):
        def generate(self, system_prompt, user_prompt, model, temperature, on_delta=None):
            calls.append(user_prompt)
            if "Sandbox Error Feedback" in user_prompt:
                # Correct the code on the second try
                return """
Fixed:
```python-run
print("Fixed result")
```
"""
            # First try has an error
            return """
Buggy code:
```python-run
raise RuntimeError("test error")
```
"""

    config = AppConfig(
        agents={
            "writer": AgentConfig(
                role="Writer", model="mock", temperature=0.0,
                system_prompt="Writer prompt.",
            ),
        },
        pipeline=PipelineConfig(
            sections=[
                SectionPrompt(name="theory", topic="Theory", instruction="Explain."),
            ],
            academic_mode=True,
        ),
        quality_gate=QualityGateConfig(
            volume=VolumeGateConfig(enabled=False),
            latex=LatexGateConfig(enabled=False),
        ),
    )

    llm = SelfCorrectionMockProvider()
    writer = DefaultAgent(config.agents["writer"], llm)
    orch = Orchestrator(writer=writer, config=config)

    result = orch.run_pipeline(render_artifact=False)
    assert orch.state == PipelineState.DONE
    assert "theory" in orch.context
    assert "Fixed result" in orch.context["theory"]
    # Verify we had 3 calls to writer: plan, initial draft, then self-correction
    assert len(calls) == 3
    assert "Sandbox Error Feedback" in calls[2]
