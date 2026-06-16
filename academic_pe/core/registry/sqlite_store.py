import sqlite3
import os
import contextlib
from typing import List, Optional
from academic_pe.core.registry.store import RegistryStore
from academic_pe.core.registry.models import (
    Run, RunAgent, Artifact, RuntimeSnapshot,
    Section, Source, Evaluation, Event
)
from academic_pe.core.registry.migrations import run_migrations

class SQLiteRegistryStore(RegistryStore):
    def __init__(self, db_path: str = "exports/_metadata/academic_pe_registry.sqlite3", run_migrations_at_init: bool = True):
        self.db_path = db_path
        if run_migrations_at_init:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            conn = sqlite3.connect(self.db_path)
            try:
                run_migrations(conn)
            finally:
                conn.close()

    @contextlib.contextmanager
    def _connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def create_run(self, run: Run) -> None:
        sql = """
        INSERT INTO runs (
            run_id, kind, status, topic, instructions_preview,
            pipeline_mode, web_search_enabled, created_at, started_at,
            finished_at, output_dir, error_type, error_message, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._connection() as conn:
            conn.execute(
                sql,
                (
                    run.run_id,
                    run.kind,
                    run.status,
                    run.topic,
                    run.instructions_preview,
                    run.pipeline_mode,
                    1 if run.web_search_enabled else 0,
                    run.created_at,
                    run.started_at,
                    run.finished_at,
                    run.output_dir,
                    run.error_type,
                    run.error_message,
                    run.metadata_json,
                ),
            )

    def update_run_status(
        self,
        run_id: str,
        status: str,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        finished_at: Optional[str] = None,
        metadata_json: Optional[str] = None,
    ) -> None:
        sets = ["status = ?"]
        params = [status]
        
        if error_type is not None:
            sets.append("error_type = ?")
            params.append(error_type)
        if error_message is not None:
            sets.append("error_message = ?")
            params.append(error_message)
        if finished_at is not None:
            sets.append("finished_at = ?")
            params.append(finished_at)
        if metadata_json is not None:
            sets.append("metadata_json = ?")
            params.append(metadata_json)
            
        params.append(run_id)
        sql = f"UPDATE runs SET {', '.join(sets)} WHERE run_id = ?"
        with self._connection() as conn:
            conn.execute(sql, tuple(params))

    def add_agent(self, agent: RunAgent) -> None:
        sql = """
        INSERT INTO run_agents (
            run_id, role, provider, model, temperature,
            agent_type, self_critique_enabled, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._connection() as conn:
            conn.execute(
                sql,
                (
                    agent.run_id,
                    agent.role,
                    agent.provider,
                    agent.model,
                    agent.temperature,
                    agent.agent_type,
                    1 if agent.self_critique_enabled else 0,
                    agent.metadata_json,
                ),
            )

    def add_artifact(self, artifact: Artifact) -> None:
        sql = """
        INSERT INTO artifacts (
            run_id, artifact_type, path, relative_path, filename,
            mime_type, size_bytes, sha256, created_at, is_diagnostic, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._connection() as conn:
            conn.execute(
                sql,
                (
                    artifact.run_id,
                    artifact.artifact_type,
                    artifact.path,
                    artifact.relative_path,
                    artifact.filename,
                    artifact.mime_type,
                    artifact.size_bytes,
                    artifact.sha256,
                    artifact.created_at,
                    1 if artifact.is_diagnostic else 0,
                    artifact.metadata_json,
                ),
            )

    def add_runtime_snapshot(self, snapshot: RuntimeSnapshot) -> None:
        sql = """
        INSERT INTO runtime_snapshots (
            run_id, snapshot_type, version, fingerprint, metadata_json
        ) VALUES (?, ?, ?, ?, ?)
        """
        with self._connection() as conn:
            conn.execute(
                sql,
                (
                    snapshot.run_id,
                    snapshot.snapshot_type,
                    snapshot.version,
                    snapshot.fingerprint,
                    snapshot.metadata_json,
                ),
            )

    def add_section(self, section: Section) -> None:
        sql = """
        INSERT INTO sections (
            run_id, name, title, semantic_role, heading_policy,
            char_count, order_index, content_path, content_sha256, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._connection() as conn:
            conn.execute(
                sql,
                (
                    section.run_id,
                    section.name,
                    section.title,
                    section.semantic_role,
                    section.heading_policy,
                    section.char_count,
                    section.order_index,
                    section.content_path,
                    section.content_sha256,
                    section.metadata_json,
                ),
            )

    def add_source(self, source: Source) -> None:
        sql = """
        INSERT INTO sources (
            run_id, source_type, title, url, path, sha256, used_by, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._connection() as conn:
            conn.execute(
                sql,
                (
                    source.run_id,
                    source.source_type,
                    source.title,
                    source.url,
                    source.path,
                    source.sha256,
                    source.used_by,
                    source.metadata_json,
                ),
            )

    def add_evaluation(self, evaluation: Evaluation) -> None:
        sql = """
        INSERT INTO evaluations (
            run_id, eval_type, status, summary, result_path, metadata_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        with self._connection() as conn:
            conn.execute(
                sql,
                (
                    evaluation.run_id,
                    evaluation.eval_type,
                    evaluation.status,
                    evaluation.summary,
                    evaluation.result_path,
                    evaluation.metadata_json,
                    evaluation.created_at,
                ),
            )

    def add_event(self, event: Event) -> None:
        sql = """
        INSERT INTO events (
            run_id, event_type, stage, message, created_at, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?)
        """
        with self._connection() as conn:
            conn.execute(
                sql,
                (
                    event.run_id,
                    event.event_type,
                    event.stage,
                    event.message,
                    event.created_at,
                    event.metadata_json,
                ),
            )

    def get_run(self, run_id: str) -> Optional[Run]:
        sql = "SELECT * FROM runs WHERE run_id = ?"
        with self._connection() as conn:
            row = conn.execute(sql, (run_id,)).fetchone()
            if row:
                return Run(
                    id=row["id"],
                    run_id=row["run_id"],
                    kind=row["kind"],
                    status=row["status"],
                    topic=row["topic"],
                    instructions_preview=row["instructions_preview"],
                    pipeline_mode=row["pipeline_mode"],
                    web_search_enabled=bool(row["web_search_enabled"]),
                    created_at=row["created_at"],
                    started_at=row["started_at"],
                    finished_at=row["finished_at"],
                    output_dir=row["output_dir"],
                    error_type=row["error_type"],
                    error_message=row["error_message"],
                    metadata_json=row["metadata_json"],
                )
        return None

    def list_runs(
        self,
        kind: Optional[str] = None,
        status: Optional[str] = None,
        pipeline_mode: Optional[str] = None,
        template_id: Optional[str] = None,
        artifact_type: Optional[str] = None,
        created_date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Run]:
        conditions = []
        params = []
        if kind is not None:
            conditions.append("kind = ?")
            params.append(kind)
        if status is not None:
            conditions.append("status = ?")
            params.append(status)
        if pipeline_mode is not None:
            conditions.append("pipeline_mode = ?")
            params.append(pipeline_mode)
        if template_id is not None:
            conditions.append("json_extract(metadata_json, '$.template_id') = ?")
            params.append(template_id)
        if artifact_type is not None:
            conditions.append("run_id IN (SELECT DISTINCT run_id FROM artifacts WHERE artifact_type = ?)")
            params.append(artifact_type)
        if created_date is not None:
            if len(created_date) < 10:
                conditions.append("created_at LIKE ?")
                params.append(f"{created_date}%")
            else:
                conditions.append("date(created_at) = ?")
                params.append(created_date)
            
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM runs {where} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        runs = []
        with self._connection() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
            for row in rows:
                runs.append(
                    Run(
                        id=row["id"],
                        run_id=row["run_id"],
                        kind=row["kind"],
                        status=row["status"],
                        topic=row["topic"],
                        instructions_preview=row["instructions_preview"],
                        pipeline_mode=row["pipeline_mode"],
                        web_search_enabled=bool(row["web_search_enabled"]),
                        created_at=row["created_at"],
                        started_at=row["started_at"],
                        finished_at=row["finished_at"],
                        output_dir=row["output_dir"],
                        error_type=row["error_type"],
                        error_message=row["error_message"],
                        metadata_json=row["metadata_json"],
                    )
                )
        return runs

    def get_run_agents(self, run_id: str) -> List[RunAgent]:
        sql = "SELECT * FROM run_agents WHERE run_id = ? ORDER BY id ASC"
        agents = []
        with self._connection() as conn:
            rows = conn.execute(sql, (run_id,)).fetchall()
            for row in rows:
                agents.append(
                    RunAgent(
                        id=row["id"],
                        run_id=row["run_id"],
                        role=row["role"],
                        provider=row["provider"],
                        model=row["model"],
                        temperature=row["temperature"],
                        agent_type=row["agent_type"],
                        self_critique_enabled=bool(row["self_critique_enabled"]),
                        metadata_json=row["metadata_json"],
                    )
                )
        return agents

    def get_run_artifacts(self, run_id: str) -> List[Artifact]:
        sql = "SELECT * FROM artifacts WHERE run_id = ? ORDER BY id ASC"
        artifacts = []
        with self._connection() as conn:
            rows = conn.execute(sql, (run_id,)).fetchall()
            for row in rows:
                artifacts.append(
                    Artifact(
                        id=row["id"],
                        run_id=row["run_id"],
                        artifact_type=row["artifact_type"],
                        path=row["path"],
                        relative_path=row["relative_path"],
                        filename=row["filename"],
                        mime_type=row["mime_type"],
                        size_bytes=row["size_bytes"],
                        sha256=row["sha256"],
                        created_at=row["created_at"],
                        is_diagnostic=bool(row["is_diagnostic"]),
                        metadata_json=row["metadata_json"],
                    )
                )
        return artifacts

    def get_run_snapshots(self, run_id: str) -> List[RuntimeSnapshot]:
        sql = "SELECT * FROM runtime_snapshots WHERE run_id = ? ORDER BY id ASC"
        snapshots = []
        with self._connection() as conn:
            rows = conn.execute(sql, (run_id,)).fetchall()
            for row in rows:
                snapshots.append(
                    RuntimeSnapshot(
                        id=row["id"],
                        run_id=row["run_id"],
                        snapshot_type=row["snapshot_type"],
                        version=row["version"],
                        fingerprint=row["fingerprint"],
                        metadata_json=row["metadata_json"],
                    )
                )
        return snapshots

    def get_run_sections(self, run_id: str) -> List[Section]:
        sql = "SELECT * FROM sections WHERE run_id = ? ORDER BY order_index ASC"
        sections = []
        with self._connection() as conn:
            rows = conn.execute(sql, (run_id,)).fetchall()
            for row in rows:
                sections.append(
                    Section(
                        id=row["id"],
                        run_id=row["run_id"],
                        name=row["name"],
                        title=row["title"],
                        semantic_role=row["semantic_role"],
                        heading_policy=row["heading_policy"],
                        char_count=row["char_count"],
                        order_index=row["order_index"],
                        content_path=row["content_path"],
                        content_sha256=row["content_sha256"],
                        metadata_json=row["metadata_json"],
                    )
                )
        return sections

    def get_run_sources(self, run_id: str) -> List[Source]:
        sql = "SELECT * FROM sources WHERE run_id = ? ORDER BY id ASC"
        sources = []
        with self._connection() as conn:
            rows = conn.execute(sql, (run_id,)).fetchall()
            for row in rows:
                sources.append(
                    Source(
                        id=row["id"],
                        run_id=row["run_id"],
                        source_type=row["source_type"],
                        title=row["title"],
                        url=row["url"],
                        path=row["path"],
                        sha256=row["sha256"],
                        used_by=row["used_by"],
                        metadata_json=row["metadata_json"],
                    )
                )
        return sources

    def get_run_evaluations(self, run_id: str) -> List[Evaluation]:
        sql = "SELECT * FROM evaluations WHERE run_id = ? ORDER BY created_at ASC"
        evaluations = []
        with self._connection() as conn:
            rows = conn.execute(sql, (run_id,)).fetchall()
            for row in rows:
                evaluations.append(
                    Evaluation(
                        id=row["id"],
                        run_id=row["run_id"],
                        eval_type=row["eval_type"],
                        status=row["status"],
                        summary=row["summary"],
                        result_path=row["result_path"],
                        metadata_json=row["metadata_json"],
                        created_at=row["created_at"],
                    )
                )
        return evaluations

    def get_run_events(self, run_id: str) -> List[Event]:
        sql = "SELECT * FROM events WHERE run_id = ? ORDER BY created_at ASC"
        events = []
        with self._connection() as conn:
            rows = conn.execute(sql, (run_id,)).fetchall()
            for row in rows:
                events.append(
                    Event(
                        id=row["id"],
                        run_id=row["run_id"],
                        event_type=row["event_type"],
                        stage=row["stage"],
                        message=row["message"],
                        created_at=row["created_at"],
                        metadata_json=row["metadata_json"],
                    )
                )
        return events

    def update_run(self, run: Run) -> None:
        sql = """
        UPDATE runs SET
            kind = ?, status = ?, topic = ?, instructions_preview = ?,
            pipeline_mode = ?, web_search_enabled = ?, created_at = ?, started_at = ?,
            finished_at = ?, output_dir = ?, error_type = ?, error_message = ?, metadata_json = ?
        WHERE run_id = ?
        """
        with self._connection() as conn:
            conn.execute(
                sql,
                (
                    run.kind,
                    run.status,
                    run.topic,
                    run.instructions_preview,
                    run.pipeline_mode,
                    1 if run.web_search_enabled else 0,
                    run.created_at,
                    run.started_at,
                    run.finished_at,
                    run.output_dir,
                    run.error_type,
                    run.error_message,
                    run.metadata_json,
                    run.run_id,
                ),
            )

    def delete_run(self, run_id: str) -> None:
        sql = "DELETE FROM runs WHERE run_id = ?"
        with self._connection() as conn:
            conn.execute(sql, (run_id,))

    def delete_run_artifacts(self, run_id: str, artifact_type: Optional[str] = None) -> None:
        if artifact_type is None:
            sql = "DELETE FROM artifacts WHERE run_id = ?"
            params = (run_id,)
        else:
            sql = "DELETE FROM artifacts WHERE run_id = ? AND artifact_type = ?"
            params = (run_id, artifact_type)
        with self._connection() as conn:
            conn.execute(sql, params)

    def delete_run_snapshots(self, run_id: str, snapshot_type: Optional[str] = None) -> None:
        if snapshot_type is None:
            sql = "DELETE FROM runtime_snapshots WHERE run_id = ?"
            params = (run_id,)
        else:
            sql = "DELETE FROM runtime_snapshots WHERE run_id = ? AND snapshot_type = ?"
            params = (run_id, snapshot_type)
        with self._connection() as conn:
            conn.execute(sql, params)

    def delete_run_sources(self, run_id: str, source_type: Optional[str] = None) -> None:
        if source_type is None:
            sql = "DELETE FROM sources WHERE run_id = ?"
            params = (run_id,)
        else:
            sql = "DELETE FROM sources WHERE run_id = ? AND source_type = ?"
            params = (run_id, source_type)
        with self._connection() as conn:
            conn.execute(sql, params)


class NoopRegistryStore(RegistryStore):
    def create_run(self, run: Run) -> None:
        pass

    def update_run_status(
        self,
        run_id: str,
        status: str,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        finished_at: Optional[str] = None,
        metadata_json: Optional[str] = None,
    ) -> None:
        pass

    def add_agent(self, agent: RunAgent) -> None:
        pass

    def add_artifact(self, artifact: Artifact) -> None:
        pass

    def add_runtime_snapshot(self, snapshot: RuntimeSnapshot) -> None:
        pass

    def add_section(self, section: Section) -> None:
        pass

    def add_source(self, source: Source) -> None:
        pass

    def add_evaluation(self, evaluation: Evaluation) -> None:
        pass

    def add_event(self, event: Event) -> None:
        pass

    def get_run(self, run_id: str) -> Optional[Run]:
        return None

    def list_runs(
        self,
        kind: Optional[str] = None,
        status: Optional[str] = None,
        pipeline_mode: Optional[str] = None,
        template_id: Optional[str] = None,
        artifact_type: Optional[str] = None,
        created_date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Run]:
        return []

    def get_run_agents(self, run_id: str) -> List[RunAgent]:
        return []

    def get_run_artifacts(self, run_id: str) -> List[Artifact]:
        return []

    def get_run_snapshots(self, run_id: str) -> List[RuntimeSnapshot]:
        return []

    def get_run_sections(self, run_id: str) -> List[Section]:
        return []

    def get_run_sources(self, run_id: str) -> List[Source]:
        return []

    def get_run_evaluations(self, run_id: str) -> List[Evaluation]:
        return []

    def get_run_events(self, run_id: str) -> List[Event]:
        return []

    def update_run(self, run: Run) -> None:
        pass

    def delete_run(self, run_id: str) -> None:
        pass

    def delete_run_artifacts(self, run_id: str, artifact_type: Optional[str] = None) -> None:
        pass

    def delete_run_snapshots(self, run_id: str, snapshot_type: Optional[str] = None) -> None:
        pass

    def delete_run_sources(self, run_id: str, source_type: Optional[str] = None) -> None:
        pass
