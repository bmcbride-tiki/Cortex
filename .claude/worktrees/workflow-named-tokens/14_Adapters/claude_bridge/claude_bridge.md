---
tool_id: 'claude_bridge'
title: 'Claude Bridge'
classification: '00_System_Core/adapters'
data_policy: 'internal'
execution_engine: 'mock'
tags: [type/module, domain/system-core, tier/zero-input, function/mock-adapter, scope/claude, connects/core-router, connects/workflow-engine]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# claude-bridge

> **Status:** Mock-only. No `ANTHROPIC_API_KEY` is configured for this project yet, so every action simulates a realistic response rather than calling the real Claude API.

## Purpose

Lets [[workflow_engine]]'s `function_claude_ask` node send a prompt to
Claude and get a response, mirroring [[gemini_bridge]]/[[notebooklm_bridge]]'s
contract shape so workflows can be built and tested end-to-end before real
credentials exist.

## Processing Logic

### `MOCK_MODE` (env var `CLAUDE_MOCK_MODE`, default on)

With `MOCK_MODE` off and no real backend wired in, `ask` fails clearly
(`NOT_CONFIGURED_MESSAGE`) instead of pretending to succeed.

### Actions (JSON payload, positional CLI arg)

* **`ask`** — params: `prompt`. Returns a single clearly labeled
  `[MOCK Claude response ...]` string.

## Output

One JSON line on stdout per invocation: `{"success": true, "response": ...}`
or `{"success": false, "response": "<error>"}` (non-zero exit code on
failure) — same contract as every other adapter in this project.

## Notes for AI reuse

* Wiring in a real API call: use the `anthropic` Python SDK's
  `client.messages.create(model=..., messages=[{"role": "user", "content": prompt}], max_tokens=...)`
  inside `ask()` when `MOCK_MODE` is off and a key is available. Nothing
  else in this file (the CLI contract, `main()`'s dispatch) needs to change.
* Claude is **not yet in this project's official information-security
  classification list** (see `00_System/model_classifications.py`) — it
  currently defaults to the most conservative level (`public`) until
  officially classified. Update `MODEL_CLASSIFICATIONS["claude"]` there the
  moment an official level is assigned.

## Required dependencies

None beyond the Python standard library while mock-mode is active. A real
integration would add `anthropic` to `requirements.txt`.
