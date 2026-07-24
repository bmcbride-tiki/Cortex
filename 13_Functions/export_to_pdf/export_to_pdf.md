---
tool_id: 'export_to_pdf'
title: 'Export to PDF'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/export, scope/pdf]
---

# export-to-pdf

> **Status:** Active. Standalone-capable utility, also drag-and-droppable onto the Workflow Builder canvas (category `09_Functions`).

## Purpose

Writes text into a new `.pdf` file. Moved out of `workflow_engine.py`'s
built-in function ladder (`function_export_pdf`) since it needs nothing
from a graph.

## Input

One JSON payload, positional CLI arg: `{"text": "...", "output_dir": "...", "filename": "..."}`.
`filename` is optional (auto-generated from a timestamp if blank); `.pdf`
is appended automatically if missing.

## Processing Logic

Writes `text` via `fpdf2`, one `multi_cell` per line.

## Output

`{"success": true, "file_path": "..."}` on success, or
`{"success": false, "response": "<error>"}` (non-zero exit code) on
failure.

## Known Limitation

`fpdf2`'s built-in font only supports Latin-1 (roughly Western European)
characters — text with characters outside that range fails to export with
a clear error rather than a cryptic library crash.

## Notes for AI reuse

Dispatched by [[workflow_engine]] via the generic `09_Functions` path (same
mechanism as Task/Process/Adapter) — see [[core_router]].
