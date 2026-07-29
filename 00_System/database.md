---
tool_id: 'database'
title: 'Database'
classification: '00_System_Core'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/module, domain/system-core, tier/zero-input, function/schema-management, scope/brain-state-db, connects/server, connects/query-schedules, connects/airgap-adapter, connects/workflow-engine]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# database

> **Status:** Active. Both an importable module (`get_db_connection`, `initialize_database`) and a runnable script (`python database.py` re-applies the schema and exits).

## Purpose

Owns the single SQLite database for the whole vault, `00_System_Core/brain_state.db`. Every other tool that touches structured data (class schedules, exam marks, contacts, transcripts, process tags, the Agentic Workflow Uploader's templates, saved [[workflow_engine|Workflow Builder]] diagrams, etc.) does so exclusively through `get_db_connection()` from this module -- there is no other place a table gets created. [[server]] is the primary consumer (nearly every `/api/*` route opens a connection here). Note: [[query_schedules]] deliberately duplicates its own `get_db_connection()` rather than importing this one -- see that file's own notes.

**⚠ Known gap found during this documentation pass:** [[airgap_adapter]]'s `log_ingestion_event()` inserts into a table called `governance_lineage`, but no `CREATE TABLE` for `governance_lineage` exists anywhere in this file (or anywhere else in the codebase). Calling that method against a freshly-initialized database will fail with `sqlite3.OperationalError: no such table: governance_lineage`. If the air-gap adapter's audit logging is meant to work, a `CREATE TABLE IF NOT EXISTS governance_lineage (...)` block needs to be added to `initialize_database()` here.

## Processing Logic

### `get_db_connection() -> sqlite3.Connection`

Opens `brain_state.db` with `row_factory = sqlite3.Row` (so query results support both index and column-name access, e.g. `row["name"]`). Does **not** call `initialize_database()` itself -- callers must ensure the schema exists first (normally handled once by `server.py`'s FastAPI lifespan on startup).

### `initialize_database() -> None`

Idempotent; safe to run repeatedly against an existing database. Runs, in order:

1. `PRAGMA foreign_keys = ON;`
2. Creates every table with `CREATE TABLE IF NOT EXISTS` (so it never clobbers existing data), currently: `global_search_index` (FTS5 virtual table), `historical_registrations`, `projected_registrations`, `training_classes`, `apprentice_exam_attempts`, `apprentice_section_scores`, `exam_pass_fail_aggregates`, `transcripts_metadata`, `contacts`, `class_schedules`, `process_tags`, `process_tag_links`, `abc_templates`, `abc_uploader_settings`, `workflow_definitions` (saved Workflow Builder diagrams, see [[workflow_engine]]/[[server]]), `documents_metadata`, `workflow_checkpoints` (the "Awaiting Review" human-in-the-loop queue a workflow's Review Gate/checkpoint node writes to -- **added to this list during this documentation pass**, it was previously undocumented here despite [[server]]'s `/api/workflow-checkpoints` endpoints depending on it).
3. Runs targeted `ALTER TABLE ... ADD COLUMN` migrations for columns added after a table's initial release, guarded by a `PRAGMA table_info` check first (e.g. `abc_templates.content`, added when the Agentic Workflow Uploader moved from on-disk template files to storing JSON text directly in the database). `process_tag_links.category` is the same idea but needs a full table rebuild instead of a plain `ADD COLUMN`, since it joined an existing `PRIMARY KEY` (SQLite can't alter a PK in place) -- old rows are preserved as `category='process'`.
4. Creates performance indexes (`CREATE INDEX IF NOT EXISTS`) on the columns actually filtered/joined on elsewhere (trade/period, school-year/trade, ait_id/exam_date, class_code/ait_id/exam_date, contact trade/email).
5. Seeds baseline demo data only when the relevant table is empty (`historical_registrations`, `contacts`, `process_tags`) -- keeps local development/testing instant without requiring a real data import first, and is naturally idempotent since it checks `COUNT(*) == 0` before inserting.
6. Commits and closes the connection.

## Output

* The live schema inside `brain_state.db` (gitignored via `*.db`, never checked in).
* Console message `[INIT] Database schemas successfully established with baseline data seeds.` when run directly.

## Notes for AI reuse

To add a new table: add its `CREATE TABLE IF NOT EXISTS` block to `initialize_database()`, following the existing numbered-comment convention (`# N. <Table Purpose>`), then add any indexes it needs. If a column gets added to an *existing* table later, add a `PRAGMA table_info` + `ALTER TABLE` migration guard rather than editing the `CREATE TABLE` alone -- the `CREATE TABLE IF NOT EXISTS` won't touch a table that already exists on disk.
