---
tool_id: 'write_powerpoint'
title: 'Write PowerPoint'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/export, scope/pptx]
---

# write-powerpoint

> **Status:** Active. Standalone-capable utility, also drag-and-droppable onto the Workflow Builder canvas (category `09_Functions`).

## Purpose

Creates a new `.pptx` file from text, one slide per block. PowerPoint had
no read/write support anywhere in this project before this — `python-pptx`
is a new dependency (see `requirements.txt`).

## Input

One JSON payload, positional CLI arg: `{"text": "...", "output_dir": "...", "filename": "..."}`.
`filename` is optional (auto-generated from a timestamp if blank); `.pptx`
is appended automatically if missing.

## Processing Logic

Splits `text` on blank lines into blocks. For each block, the first line
becomes the slide title and the remaining lines become the slide body,
using the default "Title and Content" layout.

## Output

`{"success": true, "file_path": "..."}` on success, or
`{"success": false, "response": "<error>"}` (non-zero exit code) on
failure.

## Notes for AI reuse

Dispatched by [[workflow_engine]] via the generic `09_Functions` path (same
mechanism as Task/Process/Adapter) — see [[core_router]]. Pairs with
[[m365_graph_bridge]]'s `upload_file` action for pushing a generated
`.pptx` into OneDrive/SharePoint.

## Required dependencies

`python-pptx` (added to `requirements.txt`).
