---
tool_id: 'ask_copilot_agent'
title: 'Ask Copilot Agent'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'browser_automation'
tags: [type/task, domain/04-task, tier/zero-input, function/copilot, scope/agents]
---

# ask-copilot-agent

> **Status:** Active. Requires settings (`agent_name`, `prompt`) before running — a Task, not a Process. **Real browser automation, not mocked** — requires a signed-in session.

## Purpose

Grounds a message to a specific @-mentioned M365 Copilot agent (e.g.
Hal-9000) and captures its response. Uses your signed-in Edge session via
[[copilot_bridge]] — no API key.

## Input

One JSON payload, positional CLI arg: `{"agent_name": "...", "prompt": "..."}`.
Get `agent_name` from [[list_copilot_agents]].

## Processing Logic

Imports and calls `ask_agent()` directly from
`14_Adapters/copilot_bridge/copilot_bridge.py` (same Python environment,
no subprocess) — a real Playwright browser automation call, not a mock.

## Output

`{"success": true, "response": "..."}`.

## Notes for AI reuse

Tagged `model: "copilot"` in `server.py`'s `TOOL_MODELS`. Supersedes the
retired `function_copilot_agent_ask` built-in engine function. Has real
side effects (launches a headless Edge session) — don't run it
speculatively in automated tests; mock `ask_agent` instead.
