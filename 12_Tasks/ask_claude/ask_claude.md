---
tool_id: 'ask_claude'
title: 'Ask Claude'
classification: '06_Tasks'
data_policy: 'public'
execution_engine: 'mock'
tags: [type/task, domain/04-task, tier/zero-input, function/claude]
---

# ask-claude

> **Status:** Active. Requires a setting (`prompt`) before running — a Task, not a Process. **Mock-mode** — no ANTHROPIC_API_KEY configured yet.

## Purpose

Sends a prompt to Anthropic Claude and captures its response. Uses
[[claude_bridge]] directly — mock-mode until a real ANTHROPIC_API_KEY
exists.

## Input

One JSON payload, positional CLI arg: `{"prompt": "..."}`.

## Processing Logic

Imports and calls `ask()` directly from
`14_Adapters/claude_bridge/claude_bridge.py` (same Python environment, no
subprocess). Returns a `[MOCK Claude response] ...` placeholder while
`CLAUDE_MOCK_MODE` is on (the default).

## Output

`{"success": true, "response": "..."}`.

## Notes for AI reuse

Tagged `model: "claude"` in `server.py`'s `TOOL_MODELS`. Sibling to the
Workflow Builder's existing "Claude Processor" function node
(`function_claude_ask` in `FUNCTIONS_REGISTRY`) — same underlying
`claude_bridge.ask()` call, now also independently runnable outside a
workflow. Has no real side effects in mock mode; safe to run in automated
tests.
