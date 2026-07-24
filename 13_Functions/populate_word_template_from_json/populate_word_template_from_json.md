---
tool_id: 'populate_word_template_from_json'
title: 'Populate Word Template from JSON'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/template, scope/docx, scope/json]
---

# populate-word-template-from-json

> **Status:** Active. Standalone-capable utility, also drag-and-droppable onto the Workflow Builder canvas (category `09_Functions`) — a bridge/transform Function, not an M365 connector.

## Purpose

Fills a `.docx` template's `{{key}}` placeholders from a JSON object's
keys — one placeholder per key (e.g. `{{name}}`, `{{date}}`, `{{trade}}`).
Distinct from [[fill_docx_template]], which replaces a single
`{{ content }}` token with plain text; this one is for templates with
several distinct named fields.

## Input

One JSON payload, positional CLI arg:
`{"data": {"name": "...", "date": "..."}, "template_path": "...", "output_dir": "..."}`.
`output_dir` is optional (defaults to the template's own folder).

## Processing Logic

1. Opens `template_path` (must exist).
2. For each key in `data`, replaces every `{{ key }}` / `{{key}}` token
   found in the document's paragraph runs with `str(value)`.
3. Saves the result as a new, timestamp-named `.docx` in `output_dir`.

## Output

`{"success": true, "file_path": "..."}` on success, or
`{"success": false, "response": "<error>"}` (non-zero exit code) if
`template_path` is missing/not given or `data` isn't a non-empty object.

## Notes for AI reuse

Dispatched by [[workflow_engine]] via the generic `09_Functions` path (same
mechanism as Task/Process/Adapter) — see [[core_router]]. Pairs with
[[download_m365_file]]/[[upload_m365_file]] for "fetch template from
OneDrive, populate it, push the result back" workflows.
