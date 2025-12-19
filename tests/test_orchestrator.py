from src.core.orchestrator import Orchestrator, PipelineState
import os

def test_pipeline_execution():
    """
    Runs the full pipeline in MOCK mode to verify state transitions and file generation.
    """
    # Initialize Orchestrator
    orch = Orchestrator("config/agents.yaml")

    # Check initial state
    assert orch.state == PipelineState.INIT

    # Run
    output_file = orch.run_pipeline()

    # Verify final state
    assert orch.state == PipelineState.DONE

    # Verify artifact creation
    assert output_file == "Final_Academic_Paper.docx"
    assert os.path.exists(output_file)

    # Verify content was populated (even if mock)
    assert 'theory' in orch.context
    assert 'calculation' in orch.context

    # Cleanup
    if os.path.exists(output_file):
        os.remove(output_file)
