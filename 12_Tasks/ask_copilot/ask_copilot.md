---
tool_id: 'ask_copilot'
title: 'Ask Copilot'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'browser_automation'
tags: [type/task, domain/04-task, tier/zero-input, function/copilot]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# ask-copilot

> **Status:** Active. Requires a setting (`prompt`) before running — a Task, not a Process. **Real browser automation, not mocked** — requires a signed-in session.

## Purpose

Sends a prompt to M365 Copilot and captures its response. Uses your
signed-in Edge session via [[copilot_bridge]] — no API key. Requires a
completed "Initialize Session Auth" run first.

## Input

One JSON payload, positional CLI arg: `{"prompt": "..."}`.

## Processing Logic

Imports and calls `ask_copilot()` directly from
`14_Adapters/copilot_bridge/copilot_bridge.py` (same Python environment,
no subprocess) — a real Playwright browser automation call, not a mock.

## Output

`{"success": true, "response": "..."}`.

## Notes for AI reuse

Tagged `model: "copilot"` in `server.py`'s `TOOL_MODELS`. Supersedes the
retired `builtin_ai_processor` built-in engine function — same underlying
call, now a real, independently-runnable Task. Has real side effects
(launches a headless Edge session) — don't run it speculatively in
automated tests; mock `ask_copilot` instead.
