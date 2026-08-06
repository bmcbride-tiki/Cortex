---
tool_id: 'split_text'
title: 'Split Text'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/string-op]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# split-text

> **Status:** Active. Standalone-capable utility, also drag-and-droppable onto the Workflow Builder canvas (category `09_Functions`).

## Purpose

Splits text on a delimiter and returns the segment at a given index. Moved
out of `workflow_engine.py`'s built-in function ladder (`function_split`)
since it needs nothing from a graph — a plain string operation.

## Input

One JSON payload, positional CLI arg: `{"text": "...", "delimiter": "\n", "index": 0}`.
`delimiter` defaults to `\n`; `index` defaults to `0`.

## Processing Logic

`text.split(delimiter)[index]`. Fails clearly if `index` is out of range
for the resulting segment count.

## Output

`{"success": true, "text": "..."}` on success, or
`{"success": false, "response": "<error>"}` (non-zero exit code) if the
index is out of range.

## Notes for AI reuse

Dispatched by [[workflow_engine]] via the generic `09_Functions` path (same
mechanism as Task/Process/Adapter) — see [[core_router]].
