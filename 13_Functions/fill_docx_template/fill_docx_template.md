---
tool_id: 'fill_docx_template'
title: 'Fill Docx Template'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/template, scope/docx]
---

# fill-docx-template

> **Status:** Active. Standalone-capable utility, also drag-and-droppable onto the Workflow Builder canvas (category `09_Functions`).

## Purpose

Fills `{{ content }}` tokens in a `.docx` template with given text and
writes the completed file. Moved out of `workflow_engine.py`'s built-in
function ladder (`builtin_template_generator`, `_run_template_generator`)
since it needs nothing from a graph.

## Input

One JSON payload, positional CLI arg:
`{"content_text": "...", "template_path": "...", "output_dir": "..."}`.
`output_dir` is optional (defaults to `02_vault/generated`).

## Processing Logic

1. Opens `template_path` (must exist).
2. Replaces every `{{ content }}` / `{{content}}` token found in the
   document's paragraph runs with `content_text`.
3. Saves the result as a new, timestamp-named `.docx` in `output_dir`.

## Output

`{"success": true, "file_path": "..."}` on success, or
`{"success": false, "response": "<error>"}` (non-zero exit code) if
`template_path` is missing or not given.

## Notes for AI reuse

Dispatched by [[workflow_engine]] via the generic `09_Functions` path (same
mechanism as Task/Process/Adapter) — see [[core_router]].
