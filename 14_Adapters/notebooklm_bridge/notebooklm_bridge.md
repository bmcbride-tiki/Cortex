---
tool_id: 'notebooklm_bridge'
title: 'NotebookLM Bridge'
classification: '00_System_Core/adapters'
data_policy: 'internal'
execution_engine: 'mock'
tags: [type/module, domain/system-core, tier/zero-input, function/mock-adapter, scope/notebooklm, connects/core-router, connects/workflow-engine]
---

# notebooklm-bridge

> **Status:** Mock-only. There is no public API or MCP access for Google NotebookLM as of this writing (see [[gemini_bridge]]'s own note on this), so every action here simulates realistic responses rather than calling a real backend.

## Purpose

Lets [[workflow_engine]] create a NotebookLM notebook, upload sources
(PDF/Docx/JSON files), and run a sequence of questions against it —
mirroring the real product's capabilities so workflows that need this step
can be built, wired, and tested end-to-end today. The action names,
parameters, and JSON response shape are the real contract; only the inside
of each action function needs to change once real API/MCP access exists.

## Processing Logic

### `MOCK_MODE` (env var `NOTEBOOKLM_MOCK_MODE`, default on)

A separate concern from `workflow_engine.py`'s own `dry_run`: `dry_run`
means "don't call any adapter at all yet"; `MOCK_MODE` means "this adapter
has no real backend to call yet, so simulate one realistically." With
`MOCK_MODE` off and no real backend wired in, every action fails clearly
(`NOT_CONFIGURED_MESSAGE`) instead of pretending to succeed.

### Actions (JSON payload, positional CLI arg)

Always prints exactly one JSON line to stdout: `{"success": true, ...}` or
`{"success": false, "response": "<error>"}` (non-zero exit code on failure)
— same contract as [[gemini_bridge]]/[[copilot_bridge]].

* **`create_notebook`** — params: `title`. Returns a fake `notebook_id`
  (`nb_<uuid hex>`).
* **`upload_sources`** — params: `notebook_id`, `file_paths` (list). Still
  validates every path is a real file on disk even in mock mode, so a typo'd
  path surfaces immediately. Returns a `sources` list (`source_id`,
  `filename`, `status`).
* **`ask`** — params: `notebook_id`, `prompt`. Returns a single clearly
  labeled `[MOCK NotebookLM response ...]` string.
* **`prompt_loop`** — params: `notebook_id`, `prompts` (list). Calls `ask`
  once per prompt in order, returns `qa_pairs` (`prompt` + `response` per
  entry) — this is what `workflow_engine.py`'s
  `function_notebooklm_prompt_loop` node output becomes `stem.json` from,
  via the existing `function_export_json` node.

## Output

One JSON line on stdout per invocation (see Actions above). Non-zero exit
code whenever `"success": false`.

## Notes for AI reuse

See [[workflow_engine]] for the 3 Workflow Builder nodes that call into this
file (`function_notebooklm_create`, `function_notebooklm_upload_sources`,
`function_notebooklm_prompt_loop`), and [[core_router]] for how the dispatch
itself works (`08_Adapters` category, same as every other adapter).

## Required dependencies

None beyond the Python standard library — no new entry needed in
`requirements.txt`.
