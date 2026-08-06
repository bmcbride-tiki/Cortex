---
tool_id: 'export_to_json'
title: 'Export to JSON'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/export, scope/json]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# export-to-json

> **Status:** Active. Standalone-capable utility, also drag-and-droppable onto the Workflow Builder canvas (category `09_Functions`).

## Purpose

Writes text out to a new `.json` file. If the text is already valid JSON,
it's re-saved neatly formatted; if not, it's wrapped in `{"content": ...}`
so the output file is always valid JSON either way. Moved out of
`workflow_engine.py`'s built-in function ladder (where it lived as
`function_export_json`) since it needs nothing from a graph — same logic,
now a real, independently runnable script.

## Input

One JSON payload, positional CLI arg: `{"text": "...", "output_dir": "...", "filename": "..."}`.
`filename` is optional (auto-generated from a timestamp if blank); `.json`
is appended automatically if missing.

## Processing Logic

1. Parse `text` as JSON; if invalid, wrap it as `{"content": text}`.
2. Write the result, pretty-printed, to `output_dir/filename.json`.

## Output

`{"success": true, "file_path": "..."}` on success, or
`{"success": false, "response": "<error>"}` (non-zero exit code) on failure.

## Notes for AI reuse

Dispatched by [[workflow_engine]] via the generic `09_Functions` path (same
mechanism as Task/Process/Adapter) — see [[core_router]].
