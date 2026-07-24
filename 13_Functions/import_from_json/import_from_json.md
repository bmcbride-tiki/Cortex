---
tool_id: 'import_from_json'
title: 'Import from JSON'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/import, scope/json]
---

# import-from-json

> **Status:** Active. Standalone-capable utility, also drag-and-droppable onto the Workflow Builder canvas (category `09_Functions`).

## Purpose

Reads a local `.json` file and returns its pretty-printed contents as text.
Moved out of `workflow_engine.py`'s built-in function ladder
(`function_import_json`) since it needs nothing from a graph.

## Input

One JSON payload, positional CLI arg: `{"file_path": "..."}`.

## Processing Logic

Reads and parses the file, re-serializes it pretty-printed.

## Output

`{"success": true, "text": "..."}` on success, or
`{"success": false, "response": "<error>"}` (non-zero exit code) if the
file is missing or isn't valid JSON.

## Notes for AI reuse

Dispatched by [[workflow_engine]] via the generic `09_Functions` path (same
mechanism as Task/Process/Adapter) — see [[core_router]].
