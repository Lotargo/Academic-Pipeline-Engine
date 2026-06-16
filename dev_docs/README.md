# Developer Notes

`dev_docs/` contains engineering notes, sprint plans, implementation decisions, smoke notes and design scratchpads for Academic Pipeline Engine.

These files are intentionally kept in the repository because they show how the project evolved and why certain architecture choices were made. They are not the polished public documentation layer. For the project overview, start with:

- [`README.md`](../README.md)
- [`docs/USAGE_GUIDE.md`](../docs/USAGE_GUIDE.md)
- [`docs/PROJECT_CAPABILITIES.md`](../docs/PROJECT_CAPABILITIES.md)
- [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md)

## Project Intent

Academic Pipeline Engine was created first as a local-first tool for real work: helping people prepare, continue, review and export documents with less friction. That includes personal use, study workflows, research-adjacent writing, technical notes, reports, and document-heavy tasks where a plain chat interface is not enough.

The project is deliberately not presented as a finished SaaS product. Its architecture keeps a path open for SaaS/B2B integration, but the current center of gravity is a single-user local workspace with strong document pipeline semantics.

## How To Read These Notes

- Sprint files may contain completed items, old assumptions, open questions and local validation notes.
- Some notes describe future adapters or integration paths before they are productized.
- Smoke and quality notes are diagnostic. They document behavior checks, not marketing claims.
- The SQLite registry work is implemented as the current local-first persistence layer. PostgreSQL/Redis/SaaS-style storage is treated as a future adapter path, not a current dependency.

## What Should Not Be Here

Do not commit:

- API keys or secrets;
- private user documents;
- generated exports or large runtime artifacts;
- local database files;
- raw logs that expose sensitive prompts or source material.

Runtime outputs belong under ignored `exports/` paths. Public-facing explanations belong under `docs/`.
