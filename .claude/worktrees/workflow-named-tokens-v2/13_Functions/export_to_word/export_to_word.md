---
tool_id: 'export_to_word'
title: 'Export to Word'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/export, scope/docx]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# export-to-word

> **Status:** Active. Standalone-capable utility, also drag-and-droppable onto the Workflow Builder canvas (category `09_Functions`).

## Purpose

Writes text into a new `.docx` file, one paragraph per line. Moved out of
`workflow_engine.py`'s built-in function ladder (`function_export_word`)
since it needs nothing from a graph.

## Input

One JSON payload, positional CLI arg: `{"text": "...", "output_dir": "...", "filename": "..."}`.
`filename` is optional (auto-generated from a timestamp if blank); `.docx`
is appended automatically if missing.

## Processing Logic

Splits `text` on newlines and writes each line as its own paragraph via
`python-docx`, saved to `output_dir/filename.docx`.

## Output

`{"success": true, "file_path": "..."}` on success, or
`{"success": false, "response": "<error>"}` (non-zero exit code) on failure.

## Notes for AI reuse

Dispatched by [[workflow_engine]] via the generic `09_Functions` path (same
mechanism as Task/Process/Adapter) — see [[core_router]].
