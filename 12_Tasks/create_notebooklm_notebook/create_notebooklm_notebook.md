---
tool_id: 'create_notebooklm_notebook'
title: 'Create NotebookLM Notebook'
classification: '06_Tasks'
data_policy: 'protected_a'
execution_engine: 'mock'
tags: [type/task, domain/04-task, tier/zero-input, function/notebooklm]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# create-notebooklm-notebook

> **Status:** Active. Optional setting (`title`) before running — a Task, not a Process. **Mock-mode** — no real NotebookLM API/MCP access configured yet.

## Purpose

Creates a new Google NotebookLM notebook. Uses [[notebooklm_bridge]]
directly — mock-mode until real API/MCP access exists.

## Input

One JSON payload, positional CLI arg: `{"title": "..."}` (defaults to
`"Untitled Notebook"` if blank).

## Processing Logic

Imports and calls `create_notebook()` directly from
`14_Adapters/notebooklm_bridge/notebooklm_bridge.py` (same Python
environment, no subprocess). Returns a simulated `notebook_id` (e.g.
`nb_<uuid4 hex[:12]>`) while `NOTEBOOKLM_MOCK_MODE` is on (the default).

## Output

`{"success": true, "notebook_id": "...", "title": "..."}`.

## Notes for AI reuse

Tagged `model: "notebooklm"` in `server.py`'s `TOOL_MODELS`. Sibling to the
Workflow Builder's existing "NotebookLM: Create Notebook" function node
(`function_notebooklm_create` in `FUNCTIONS_REGISTRY`) — same underlying
`notebooklm_bridge.create_notebook()` call, now also independently runnable
outside a workflow. The returned `notebook_id` feeds
[[upload_notebooklm_sources]] and [[run_notebooklm_prompt_loop]].
