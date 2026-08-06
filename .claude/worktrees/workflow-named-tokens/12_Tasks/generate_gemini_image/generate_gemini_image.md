---
tool_id: 'generate_gemini_image'
title: 'Generate Gemini Image'
classification: '06_Tasks'
data_policy: 'protected_a'
execution_engine: 'browser_automation'
tags: [type/task, domain/04-task, tier/zero-input, function/gemini]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# generate-gemini-image

> **Status:** Active. Requires settings (`prompt`, `output_dir`) before running — a Task, not a Process. **Mock-mode by default** (`GEMINI_MOCK_MODE`) — set it to `0` to use a real signed-in Gemini session.

## Purpose

Asks Google Gemini's built-in image generation to create an image from a
prompt and saves it to a local folder. Uses [[gemini_bridge]] directly —
your signed-in Gemini session, no API key, when not in mock mode.

## Input

One JSON payload, positional CLI arg: `{"prompt": "...", "output_dir": "..."}`.

## Processing Logic

Imports and calls `generate_image()` directly from
`14_Adapters/gemini_bridge/gemini_bridge.py` (same Python environment, no
subprocess). While `GEMINI_MOCK_MODE` is on (the default), writes a small
placeholder PNG-signature file into `output_dir` and returns its path
instead of launching a real browser session.

## Output

`{"success": true, "file_path": "..."}`.

## Notes for AI reuse

Tagged `model: "gemini"` in `server.py`'s `TOOL_MODELS`. Sibling to the
Workflow Builder's existing "Image Generate" function node
(`function_image_generate` in `FUNCTIONS_REGISTRY`) — same underlying
`gemini_bridge.generate_image()` call, now also independently runnable
outside a workflow.
