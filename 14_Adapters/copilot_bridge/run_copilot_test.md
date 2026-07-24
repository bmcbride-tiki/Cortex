---
tool_id: 'run_copilot_test'
title: 'Run Copilot Test (File Upload)'
classification: '00_System_Core/adapters'
data_policy: 'internal'
execution_engine: 'browser_automation'
tags: [type/script, domain/system-core, tier/manual-test, function/browser-automation, scope/m365-copilot, connects/copilot-ask]
---

# run-copilot-test

> **Status:** Active, manual test only -- not called by [[core_router]] or [[server]]. Currently broken as-shipped: its hard-coded target file (`02_vault/transcripts/copilot_test.docx`) no longer exists, since that `transcripts` folder was removed from the project. Point `TARGET_FILE` at a real file before running.

## Purpose

Manual sanity check for [[copilot_ask]]'s file-upload capability: attaches a local document to a Copilot question and asks for a 3-bullet-point summary of it, verifying both the attachment step and the normal ask-and-read-answer step still work.

## Processing Logic

Checks `TARGET_FILE` exists (exits with an error if not), then constructs a [[copilot_ask|CopilotBridge]] instance (`headless=True`) and calls `.ask(prompt_text=..., file_to_upload=TARGET_FILE, expect_file_download=False)`.

## Output

Console only: the file-existence check result, then Copilot's summary response text.

## Notes for AI reuse

This is the reference example for how to drive [[copilot_ask]]'s file-attachment path -- if file uploads ever get ported into the production adapter ([[copilot_bridge]]), this script's prompt/flags are the pattern to replicate in a new `run_copilot_bridge_test.py` or equivalent.
