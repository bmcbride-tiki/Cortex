---
tool_id: 'import_from_word'
title: 'Import from Word'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/import, scope/docx]
---

# import-from-word

> **Status:** Active. Standalone-capable utility, also drag-and-droppable onto the Workflow Builder canvas (category `09_Functions`).

## Purpose

Reads a local `.docx` file's paragraphs and returns the extracted text.
Moved out of `workflow_engine.py`'s built-in function ladder
(`function_import_word`) since it needs nothing from a graph.

## Input

One JSON payload, positional CLI arg: `{"file_path": "..."}`.

## Processing Logic

Reads every non-empty paragraph via `python-docx`, joined with newlines.
Tables are not read (paragraphs only) — use [[import_transcripts]]'s
approach as a reference if table content needs including later.

## Output

`{"success": true, "text": "..."}` on success, or
`{"success": false, "response": "<error>"}` (non-zero exit code) if the
file is missing.

## Notes for AI reuse

Dispatched by [[workflow_engine]] via the generic `09_Functions` path (same
mechanism as Task/Process/Adapter) — see [[core_router]].
