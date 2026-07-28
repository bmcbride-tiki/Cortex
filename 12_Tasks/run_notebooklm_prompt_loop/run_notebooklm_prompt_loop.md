---
tool_id: 'run_notebooklm_prompt_loop'
title: 'Run NotebookLM Prompt Loop'
classification: '06_Tasks'
data_policy: 'protected_a'
execution_engine: 'mock'
tags: [type/task, domain/04-task, tier/zero-input, function/notebooklm]
---

# run-notebooklm-prompt-loop

> **Status:** Active. Requires settings (`notebook_id`, `prompts`) before running — a Task, not a Process. **Mock-mode** — no real NotebookLM API/MCP access configured yet.

## Purpose

Asks a NotebookLM notebook a sequence of questions and collects the answers
as JSON. Uses [[notebooklm_bridge]] directly — mock-mode until real API/MCP
access exists.

## Input

One JSON payload, positional CLI arg:
`{"notebook_id": "...", "prompts": ["What is Period 1 about?"]}`.

## Processing Logic

Imports and calls `prompt_loop()` directly from
`14_Adapters/notebooklm_bridge/notebooklm_bridge.py` (same Python
environment, no subprocess), asking each prompt in order.

## Output

`{"success": true, "qa_pairs": [{"prompt": "...", "response": "..."}, ...]}`.

## Notes for AI reuse

Tagged `model: "notebooklm"` in `server.py`'s `TOOL_MODELS`. Sibling to the
Workflow Builder's existing "NotebookLM: Prompt Loop" function node
(`function_notebooklm_prompt_loop` in `FUNCTIONS_REGISTRY`) — same
underlying `notebooklm_bridge.prompt_loop()` call, now also independently
runnable outside a workflow. Typically chained after
[[create_notebooklm_notebook]] and [[upload_notebooklm_sources]]; output
feeds directly into `export_to_json` for a `stem.json` file.
