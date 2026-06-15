from typing import List, Optional
from academic_pe.core.registry.models import (
    Run, RunAgent, Artifact, RuntimeSnapshot,
    Section, Source, Evaluation, Event
)

class RegistryStore:
    def create_run(self, run: Run) -> None:
        """Create a new run record in the registry."""
        raise NotImplementedError

    def update_run_status(
        self,
        run_id: str,
        status: str,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        finished_at: Optional[str] = None,
        metadata_json: Optional[str] = None,
    ) -> None:
        """Update the status and details of an existing run."""
        raise NotImplementedError

    def add_agent(self, agent: RunAgent) -> None:
        """Associate an LLM/agent snapshot with a run."""
        raise NotImplementedError

    def add_artifact(self, artifact: Artifact) -> None:
        """Associate a generated or consumed file artifact with a run."""
        raise NotImplementedError

    def add_runtime_snapshot(self, snapshot: RuntimeSnapshot) -> None:
        """Associate a runtime snapshot with a run."""
        raise NotImplementedError

    def add_section(self, section: Section) -> None:
        """Associate a document section metadata snapshot with a run."""
        raise NotImplementedError

    def add_source(self, source: Source) -> None:
        """Associate a source (upload, web search, ocr) with a run."""
        raise NotImplementedError

    def add_evaluation(self, evaluation: Evaluation) -> None:
        """Associate an evaluation outcome (quality gate, smoke eval) with a run."""
        raise NotImplementedError

    def add_event(self, event: Event) -> None:
        """Add a progress diagnostic event associated with a run."""
        raise NotImplementedError

    def get_run(self, run_id: str) -> Optional[Run]:
        """Retrieve a specific run by its run_id."""
        raise NotImplementedError

    def list_runs(
        self,
        kind: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Run]:
        """List runs with optional filtering, sorted by created_at desc."""
        raise NotImplementedError

    def get_run_agents(self, run_id: str) -> List[RunAgent]:
        """Retrieve all agents associated with a specific run."""
        raise NotImplementedError

    def get_run_artifacts(self, run_id: str) -> List[Artifact]:
        """Retrieve all artifacts associated with a specific run."""
        raise NotImplementedError

    def get_run_snapshots(self, run_id: str) -> List[RuntimeSnapshot]:
        """Retrieve all runtime snapshots associated with a specific run."""
        raise NotImplementedError

    def get_run_sections(self, run_id: str) -> List[Section]:
        """Retrieve all sections associated with a specific run."""
        raise NotImplementedError

    def get_run_sources(self, run_id: str) -> List[Source]:
        """Retrieve all sources associated with a specific run."""
        raise NotImplementedError

    def get_run_evaluations(self, run_id: str) -> List[Evaluation]:
        """Retrieve all evaluations associated with a specific run."""
        raise NotImplementedError

    def get_run_events(self, run_id: str) -> List[Event]:
        """Retrieve all diagnostic events associated with a specific run."""
        raise NotImplementedError

    def update_run(self, run: Run) -> None:
        """Update an existing run's metadata."""
        raise NotImplementedError

    def delete_run(self, run_id: str) -> None:
        """Delete a run and all its cascaded relations from the registry."""
        raise NotImplementedError

    def delete_run_artifacts(self, run_id: str, artifact_type: Optional[str] = None) -> None:
        """Delete artifacts of a run, optionally filtered by artifact_type."""
        raise NotImplementedError

    def delete_run_snapshots(self, run_id: str, snapshot_type: Optional[str] = None) -> None:
        """Delete snapshots of a run, optionally filtered by snapshot_type."""
        raise NotImplementedError

    def delete_run_sources(self, run_id: str, source_type: Optional[str] = None) -> None:
        """Delete sources of a run, optionally filtered by source_type."""
        raise NotImplementedError
