---
tool_id: 'import_from_pdf'
title: 'Import from PDF'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/import, scope/pdf]
---

# import-from-pdf

> **Status:** Active. Standalone-capable utility, also drag-and-droppable onto the Workflow Builder canvas (category `09_Functions`).

## Purpose

Reads a local `.pdf` file's pages and returns the extracted text. Moved out
of `workflow_engine.py`'s built-in function ladder (`function_import_pdf`)
since it needs nothing from a graph.

## Input

One JSON payload, positional CLI arg: `{"file_path": "..."}`.

## Processing Logic

Reads every page's text via `pypdf`, joined with newlines. Raw text only —
table cell structure is not preserved (same limitation noted in
[[import_documents]]).

## Output

`{"success": true, "text": "..."}` on success, or
`{"success": false, "response": "<error>"}` (non-zero exit code) if the
file is missing.

## Notes for AI reuse

Dispatched by [[workflow_engine]] via the generic `09_Functions` path (same
mechanism as Task/Process/Adapter) — see [[core_router]].
