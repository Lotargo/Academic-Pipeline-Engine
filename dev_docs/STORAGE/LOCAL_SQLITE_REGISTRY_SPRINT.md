# Local SQLite Registry Sprint

Date: 2026-06-16

Related documents:

- `dev_docs/STORAGE/SYSTEM_UPDATE_STATE_STORAGE.md`
- `dev_docs/STORAGE/SYSTEM_UPDATE_TEMPLATE_LIBRARY.md`
- `dev_docs/DOCUMENT_EXPORT_AND_AGENT_TOOLS.md`
- `dev_docs/PROMPT_OCR_AND_RESEARCH_SPRINT.md`
- `dev_docs/CONTINUATION_EDITING_AND_MERGE_SPRINT.md`

## Decision

The project needs a registry layer now.

Because the current product is still local-first and single-user, the first durable registry implementation should use SQLite, not PostgreSQL or Redis.

SQLite is the near-term source of truth for run metadata and artifact relationships. The filesystem remains the blob store for generated documents, OCR outputs, research logs, quality outputs, and previews.

```text
SQLite = durable registry, indexes, relationships, statuses, metadata snapshots
exports/ = artifact files and large diagnostic payloads
config/ = active local configuration and secrets
dev_docs/ = sprint notes and implementation decisions
```

PostgreSQL and Redis remain future adapters, not immediate dependencies.

## Why This Is Needed

The project has grown beyond plain files plus ad-hoc metadata JSON:

- pipeline runs now have planner, writer, reviewer, researcher, OCR, continuation, merge, artifact manifest, and quality state;
- generated files, metadata JSON, smoke logs, quality outputs, OCR outputs, and research outputs are spread across `exports/`;
- continuation and artifact behavior depend on runtime template and runtime prompt manifest snapshots;
- it is hard to answer basic questions like "which run produced this artifact?", "which prompts/config were used?", "which quality checks passed?", or "was web research enabled?";
- generated diagnostic artifacts should be local-only, but their summaries and relationships still need to be queryable.

The registry should make project state inspectable without making the local app operationally heavier.

## Non-Goals

- Do not add PostgreSQL in this sprint.
- Do not add Redis in this sprint.
- Do not build a SaaS/multi-user storage model yet.
- Do not store full generated documents, large OCR payloads, or full research crawls directly in SQLite.
- Do not store secrets or provider API keys in SQLite.
- Do not rewrite the orchestrator around a job queue yet.
- Do not remove existing file-backed export behavior until the registry path is proven.

## Storage Boundary

SQLite stores:

- IDs, paths, timestamps, statuses, checksums, sizes;
- compact metadata snapshots;
- config/template/prompt manifest fingerprints;
- section names and high-level section metadata;
- quality verdicts and smoke scenario summaries;
- continuation source relationships;
- artifact relationships and export links.

Filesystem stores:

- DOCX/PDF/Markdown outputs;
- rendered previews;
- OCR input/output payloads;
- web research raw query results;
- smoke and quality run logs;
- any large model output that is needed only for diagnostics.

SQLite may store short previews, but not whole documents by default.

## Initial Registry Entities

### `runs`

Purpose: one pipeline execution or diagnostic scenario.

Fields:

- `id`
- `run_id`
- `kind`: `generation`, `smoke`, `quality_eval`, `ocr`, `export`
- `status`: `created`, `running`, `succeeded`, `failed`, `cancelled`
- `topic`
- `instructions_preview`
- `pipeline_mode`: `standard`, `research`, `continuation`, `ocr`, `export`
- `web_search_enabled`
- `created_at`, `started_at`, `finished_at`
- `output_dir`
- `error_type`, `error_message`
- `metadata_json`

### `run_agents`

Purpose: record which agent/provider/model participated.

Fields:

- `id`
- `run_id`
- `role`: `planner`, `writer`, `reviewer`, `researcher`, `ocr`, `verifier`
- `provider`
- `model`
- `temperature`
- `agent_type`
- `self_critique_enabled`
- `metadata_json`

### `artifacts`

Purpose: record files produced or consumed by a run.

Fields:

- `id`
- `run_id`
- `artifact_type`: `docx`, `pdf`, `markdown`, `json`, `ocr_input`, `ocr_output`, `research_log`, `quality_result`, `smoke_log`, `preview`
- `path`
- `relative_path`
- `filename`
- `mime_type`
- `size_bytes`
- `sha256`
- `created_at`
- `is_diagnostic`
- `metadata_json`

### `runtime_snapshots`

Purpose: preserve the exact runtime planning/prompting state used by a run.

Fields:

- `id`
- `run_id`
- `snapshot_type`: `config`, `runtime_template`, `runtime_prompt_manifest`, `artifact_manifest`, `continuation_source`
- `version`
- `fingerprint`
- `metadata_json`

### `sections`

Purpose: index generated document sections without storing the full document.

Fields:

- `id`
- `run_id`
- `name`
- `title`
- `semantic_role`
- `heading_policy`
- `char_count`
- `order_index`
- `content_path`
- `content_sha256`
- `metadata_json`

### `sources`

Purpose: connect uploaded/OCR/research sources to runs.

Fields:

- `id`
- `run_id`
- `source_type`: `upload`, `ocr`, `web`, `continuation`, `manual_reference`
- `title`
- `url`
- `path`
- `sha256`
- `used_by`: `planner`, `researcher`, `writer`, `reviewer`
- `metadata_json`

### `evaluations`

Purpose: record automated and manual quality outcomes.

Fields:

- `id`
- `run_id`
- `eval_type`: `quality_gate`, `contract_drift`, `smoke`, `semi_manual`, `reviewer`, `manual_review`
- `status`: `passed`, `failed`, `passed_with_notes`, `pending`
- `summary`
- `result_path`
- `metadata_json`
- `created_at`

### `events`

Purpose: compact durable event index, not full token streaming.

Fields:

- `id`
- `run_id`
- `event_type`
- `stage`
- `message`
- `created_at`
- `metadata_json`

## Adapter Shape

Add interfaces before wiring everywhere:

```python
class RegistryStore:
    def create_run(...): ...
    def update_run_status(...): ...
    def add_agent(...): ...
    def add_artifact(...): ...
    def add_runtime_snapshot(...): ...
    def add_section(...): ...
    def add_source(...): ...
    def add_evaluation(...): ...
    def add_event(...): ...
    def get_run(...): ...
    def list_runs(...): ...
```

Initial implementation:

- `SQLiteRegistryStore`
- `NoopRegistryStore` for tests and fallback
- optional file import helpers for existing `exports/_metadata/*.metadata.json`

Future implementation:

- `PostgresRegistryStore` with the same interface
- Redis-backed `EventBus`/`JobQueue` as separate interfaces, not part of the durable registry

## Suggested File Layout

```text
academic_pe/
  core/
    registry/
      __init__.py
      models.py
      store.py
      sqlite_store.py
      migrations.py
      importers.py
      checksums.py
tests/
  test_registry_sqlite.py
  test_registry_importers.py
```

Default database location:

```text
exports/_metadata/academic_pe_registry.sqlite3
```

The database file is local runtime state and should remain ignored by git.

## Migration Strategy

Use simple numbered SQL migrations first.

Requirements:

- migrations are idempotent;
- a `schema_migrations` table records applied versions;
- tests create temporary SQLite databases;
- no external migration service is required.

Alembic can be introduced later if the schema grows or if PostgreSQL becomes active.

## Implementation Phases

### Phase 1 - Registry Core

- [ ] Create registry package and models.
- [ ] Add SQLite connection/bootstrap/migrations.
- [ ] Add tables: `runs`, `run_agents`, `artifacts`, `runtime_snapshots`, `evaluations`.
- [ ] Add checksums for file artifacts.
- [ ] Add focused unit tests using temporary SQLite files.

### Phase 2 - Export Metadata Bridge

- [ ] When writing history/export metadata, also create/update a registry run.
- [ ] Register DOCX/PDF/Markdown/export metadata artifacts.
- [ ] Preserve existing JSON metadata behavior as compatibility output.
- [ ] Add importer for existing `exports/_metadata/*.metadata.json`.
- [ ] Add tests that history/export metadata and SQLite registry stay consistent.

### Phase 3 - Pipeline Integration

- [ ] Register run creation at pipeline start.
- [ ] Register planner/writer/reviewer/researcher provider/model snapshots.
- [ ] Register runtime template and runtime prompt manifest snapshots.
- [ ] Register section metadata after drafting/merge.
- [ ] Register final status and error details.
- [ ] Add tests for standard, research-enabled, and continuation runs.

### Phase 4 - Sources And Evaluations

- [ ] Register passive references and continuation source uploads.
- [ ] Register OCR input/output paths and source fingerprints.
- [ ] Register web research raw artifacts as diagnostic artifacts.
- [ ] Register quality gate, contract drift, smoke, and semi-manual eval verdicts.
- [ ] Update smoke/quality runners to write summaries into registry.

### Phase 5 - UI/API Read Model

- [ ] Add API endpoint to list registry runs with filters.
- [ ] Add API endpoint to inspect one run and linked artifacts.
- [ ] Let history/archive UI read from registry when available.
- [ ] Keep JSON metadata fallback during transition.
- [ ] Add pagination/search by status, mode, template, artifact type, and created date.

## Acceptance Criteria

- A local generation run has one durable SQLite `runs` row.
- Generated exports are discoverable from `artifacts`.
- Runtime template and prompt manifest snapshots are tied to the run.
- Research-enabled runs show researcher participation and source artifacts.
- Continuation runs show continuation source relationship and merge/evaluation metadata.
- Smoke and quality diagnostic outputs stay ignored by git but are registered as local diagnostic artifacts.
- Existing JSON history/export metadata still works during migration.
- Tests can run without PostgreSQL, Redis, or external services.

## Test Plan

- Unit: SQLite migration/bootstrap creates expected tables.
- Unit: insert/list/get run round trip.
- Unit: artifact checksum and relative path handling.
- Unit: runtime snapshot fingerprinting is stable.
- Unit: importer reads existing export metadata JSON.
- Integration: export metadata write also records registry rows.
- Integration: standard pipeline run records run, agents, snapshots, sections, and final status.
- Integration: research-enabled run records researcher and diagnostic web artifacts.
- Integration: continuation run records source relationship and evaluation metadata.

## Open Questions

- Should `exports/_metadata/academic_pe_registry.sqlite3` be the default path, or should the user be able to choose a workspace-local registry path?
- Should full section content be saved as separate Markdown files for all runs, or only when an export is produced?
- Should manual review notes live in SQLite only, or continue to be mirrored into `dev_docs` during sprint work?
- Should existing history JSON be treated as compatibility output forever, or removed after UI migrates?
- Should registry writes be best-effort during pipeline execution, or should failures fail the run?

## Future Upgrade Triggers

Move from SQLite to PostgreSQL when one or more become true:

- multi-user server mode;
- concurrent workers across processes or machines;
- remote/shared document library;
- permission model;
- large run history with server-side analytics;
- need for robust backup/restore beyond a local file.

Add Redis when one or more become true:

- async job queue;
- shared cancellation flags;
- reconnectable live progress streams;
- distributed locks;
- shared cache/rate limiting across workers.

Until then, SQLite is the right registry backend for the local product.
