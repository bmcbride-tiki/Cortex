---
tool_id: 'format_text_with_copilot'
title: 'Format Text with Copilot'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'browser_automation'
tags: [type/task, domain/04-task, tier/zero-input, function/copilot]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# format-text-with-copilot

> **Status:** Active. Requires a setting (`text`) before running — a Task, not a Process. **Real browser automation, not mocked** — requires a signed-in session.

## Purpose

Asks M365 Copilot to reformat/restyle text per style notes (e.g. into a
formal briefing note). Uses your signed-in Edge session via
[[copilot_bridge]] — no API key.

## Input

One JSON payload, positional CLI arg: `{"text": "...", "style_notes": "..."}`.
`style_notes` is optional.

## Processing Logic

Builds a "Reformat/restyle..." prompt from `text` + `style_notes`, then
calls `ask_copilot()` directly from
`14_Adapters/copilot_bridge/copilot_bridge.py` (same Python environment,
no subprocess) — a real Playwright browser automation call, not a mock.

## Output

`{"success": true, "response": "..."}`.

## Notes for AI reuse

Tagged `model: "copilot"` in `server.py`'s `TOOL_MODELS`. Supersedes the
retired `builtin_formatter` built-in engine function. Has real side
effects (launches a headless Edge session) — don't run it speculatively in
automated tests; mock `ask_copilot` instead.
