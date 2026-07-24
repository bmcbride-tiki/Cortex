---
tool_id: 'format_json'
title: 'Format JSON'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/string-op, scope/json]
---

# format-json

> **Status:** Active. Standalone-capable utility, also drag-and-droppable onto the Workflow Builder canvas (category `09_Functions`).

## Purpose

Parses text as JSON and re-serializes it pretty-printed, failing clearly if
it isn't valid JSON. Moved out of `workflow_engine.py`'s built-in function
ladder (`function_json_parse`) since it needs nothing from a graph.

## Input

One JSON payload, positional CLI arg: `{"text": "..."}`.

## Processing Logic

`json.dumps(json.loads(text), indent=2)`.

## Output

`{"success": true, "text": "..."}` on success, or
`{"success": false, "response": "Invalid JSON: ..."}` (non-zero exit code)
if parsing fails.

## Notes for AI reuse

Dispatched by [[workflow_engine]] via the generic `09_Functions` path (same
mechanism as Task/Process/Adapter) — see [[core_router]].
