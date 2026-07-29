---
tool_id: 'chatgpt_bridge'
title: 'ChatGPT Bridge'
classification: '00_System_Core/adapters'
data_policy: 'internal'
execution_engine: 'mock'
tags: [type/module, domain/system-core, tier/zero-input, function/mock-adapter, scope/chatgpt, connects/core-router, connects/workflow-engine]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# chatgpt-bridge

> **Status:** Mock-only. No `OPENAI_API_KEY` is configured for this project yet, so every action simulates a realistic response rather than calling the real OpenAI API.

## Purpose

Lets [[workflow_engine]]'s `function_chatgpt_ask` node send a prompt to
ChatGPT and get a response, mirroring [[gemini_bridge]]/[[claude_bridge]]'s
contract shape so workflows can be built and tested end-to-end before real
credentials exist.

## Processing Logic

### `MOCK_MODE` (env var `CHATGPT_MOCK_MODE`, default on)

With `MOCK_MODE` off and no real backend wired in, `ask` fails clearly
(`NOT_CONFIGURED_MESSAGE`) instead of pretending to succeed.

### Actions (JSON payload, positional CLI arg)

* **`ask`** — params: `prompt`. Returns a single clearly labeled
  `[MOCK ChatGPT response ...]` string.

## Output

One JSON line on stdout per invocation: `{"success": true, "response": ...}`
or `{"success": false, "response": "<error>"}` (non-zero exit code on
failure) — same contract as every other adapter in this project.

## Notes for AI reuse

* Wiring in a real API call: use the `openai` Python SDK's
  `client.chat.completions.create(model=..., messages=[{"role": "user", "content": prompt}])`
  inside `ask()` when `MOCK_MODE` is off and a key is available. Nothing
  else in this file (the CLI contract, `main()`'s dispatch) needs to change.
* Per this project's official information-security classification list (see
  `00_System/model_classifications.py`), ChatGPT is Public-only — "not used
  for protected information."

## Required dependencies

None beyond the Python standard library while mock-mode is active. A real
integration would add `openai` to `requirements.txt`.
