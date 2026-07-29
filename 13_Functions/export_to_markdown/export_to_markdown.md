---
tool_id: 'export_to_markdown'
title: 'Export to Markdown'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/export, scope/markdown]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# export-to-markdown

> **Status:** Active. Standalone-capable utility, also drag-and-droppable onto the Workflow Builder canvas (category `09_Functions`).

## Purpose

Writes text as-is to a new `.md` file. Moved out of `workflow_engine.py`'s
built-in function ladder (`function_export_markdown`) since it needs
nothing from a graph.

## Input

One JSON payload, positional CLI arg: `{"text": "...", "output_dir": "...", "filename": "..."}`.
`filename` is optional (auto-generated from a timestamp if blank); `.md` is
appended automatically if missing.

## Processing Logic

Writes `text` unchanged to `output_dir/filename.md`.

## Output

`{"success": true, "file_path": "..."}` on success, or
`{"success": false, "response": "<error>"}` (non-zero exit code) on failure.

## Notes for AI reuse

Dispatched by [[workflow_engine]] via the generic `09_Functions` path (same
mechanism as Task/Process/Adapter) — see [[core_router]].
