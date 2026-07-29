---
tool_id: 'generate_copilot_image'
title: 'Generate Copilot Image'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'browser_automation'
tags: [type/task, domain/04-task, tier/zero-input, function/copilot, scope/image-generation]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# generate-copilot-image

> **Status:** Active. Requires settings (`prompt`, `output_dir`) before running — a Task, not a Process. **Real browser automation, not mocked** — requires a signed-in session.

## Purpose

Asks the M365 Copilot bridge (Designer plugin) to generate an image from a
prompt and saves it to a local folder. Uses your signed-in Edge session
via [[copilot_bridge]] — no API key.

## Input

One JSON payload, positional CLI arg: `{"prompt": "...", "output_dir": "..."}`.

## Processing Logic

Imports and calls `generate_image()` directly from
`14_Adapters/copilot_bridge/copilot_bridge.py` (same Python environment,
no subprocess) — a real Playwright browser automation call, not a mock.

## Output

`{"success": true, "file_path": "..."}`.

## Notes for AI reuse

Tagged `model: "copilot"` in `server.py`'s `TOOL_MODELS`. Supersedes the
retired `function_copilot_image_generate` built-in engine function. Has
real side effects (launches a headless Edge session) — don't run it
speculatively in automated tests; mock `generate_image` instead.
