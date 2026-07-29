---
tool_id: 'read_powerpoint'
title: 'Read PowerPoint'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/import, scope/pptx]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# read-powerpoint

> **Status:** Active. Standalone-capable utility, also drag-and-droppable onto the Workflow Builder canvas (category `09_Functions`).

## Purpose

Reads a local `.pptx` file's slide text and returns it as plain text.
PowerPoint had no read/write support anywhere in this project before this
— `python-pptx` is a new dependency (see `requirements.txt`).

## Input

One JSON payload, positional CLI arg: `{"file_path": "..."}`.

## Processing Logic

For each slide, collects every shape's text frame text (skipping shapes
with no text), joined with newlines, under a `--- Slide N ---` header per
slide.

## Output

`{"success": true, "text": "..."}` on success, or
`{"success": false, "response": "<error>"}` (non-zero exit code) if the
file is missing.

## Notes for AI reuse

Dispatched by [[workflow_engine]] via the generic `09_Functions` path (same
mechanism as Task/Process/Adapter) — see [[core_router]]. Pairs with
[[m365_graph_bridge]]'s `download_file` action for reading a `.pptx` that
lives in OneDrive/SharePoint.

## Required dependencies

`python-pptx` (added to `requirements.txt`).
