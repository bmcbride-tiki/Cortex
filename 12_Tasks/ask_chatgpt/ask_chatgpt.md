---
tool_id: 'ask_chatgpt'
title: 'Ask ChatGPT'
classification: '06_Tasks'
data_policy: 'public'
execution_engine: 'mock'
tags: [type/task, domain/04-task, tier/zero-input, function/chatgpt]
---

# ask-chatgpt

> **Status:** Active. Requires a setting (`prompt`) before running — a Task, not a Process. **Mock-mode** — no OPENAI_API_KEY configured yet.

## Purpose

Sends a prompt to OpenAI ChatGPT and captures its response. Uses
[[chatgpt_bridge]] directly — mock-mode until a real OPENAI_API_KEY exists.

## Input

One JSON payload, positional CLI arg: `{"prompt": "..."}`.

## Processing Logic

Imports and calls `ask()` directly from
`14_Adapters/chatgpt_bridge/chatgpt_bridge.py` (same Python environment, no
subprocess). Returns a `[MOCK ChatGPT response] ...` placeholder while
`CHATGPT_MOCK_MODE` is on (the default).

## Output

`{"success": true, "response": "..."}`.

## Notes for AI reuse

Tagged `model: "chatgpt"` in `server.py`'s `TOOL_MODELS`. Sibling to the
Workflow Builder's existing "ChatGPT Processor" function node
(`function_chatgpt_ask` in `FUNCTIONS_REGISTRY`) — same underlying
`chatgpt_bridge.ask()` call, now also independently runnable outside a
workflow. Has no real side effects in mock mode; safe to run in automated
tests.
