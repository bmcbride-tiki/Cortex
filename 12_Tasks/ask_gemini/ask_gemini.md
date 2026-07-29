---
tool_id: 'ask_gemini'
title: 'Ask Gemini'
classification: '06_Tasks'
data_policy: 'protected_a'
execution_engine: 'browser_automation'
tags: [type/task, domain/04-task, tier/zero-input, function/gemini]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# ask-gemini

> **Status:** Active. Requires a setting (`prompt`) before running — a Task, not a Process. **Mock-mode by default** (`GEMINI_MOCK_MODE`) — set it to `0` to use a real signed-in Gemini session.

## Purpose

Sends a prompt to Google Gemini and captures its response. Set `search:
true` to run it as a full Deep Research pass instead of a normal single-turn
answer. Uses [[gemini_bridge]] directly — your signed-in Gemini session, no
API key, when not in mock mode.

## Input

One JSON payload, positional CLI arg: `{"prompt": "...", "search": false}`.

## Processing Logic

Imports and calls `ask_gemini()` directly from
`14_Adapters/gemini_bridge/gemini_bridge.py` (same Python environment, no
subprocess). Returns a `[MOCK Gemini response] ...` placeholder while
`GEMINI_MOCK_MODE` is on (the default); otherwise a real Playwright browser
automation call against the signed-in session.

## Output

`{"success": true, "response": "..."}`.

## Notes for AI reuse

Tagged `model: "gemini"` in `server.py`'s `TOOL_MODELS`. Sibling to the
Workflow Builder's existing "Gemini Processor" and "Google Search" function
nodes (`function_gemini_ask`/`function_google_search` in
`FUNCTIONS_REGISTRY`) — same underlying `gemini_bridge.ask_gemini()` call,
now also independently runnable outside a workflow, with both modes folded
into one `search` flag.
