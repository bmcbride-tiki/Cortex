---
tool_id: 'run_copilot_download_test'
title: 'Run Copilot Download Test (File Generation + Download)'
classification: '00_System_Core/adapters'
data_policy: 'internal'
execution_engine: 'browser_automation'
tags: [type/script, domain/system-core, tier/manual-test, function/browser-automation, scope/m365-copilot, connects/copilot-ask]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# run-copilot-download-test

> **Status:** Active, manual test only -- not called by [[core_router]] or [[server]].

## Purpose

Manual sanity check for [[copilot_ask]]'s file-download capability: asks Copilot to generate a Word document (a list of connected SharePoint sites) and include a download/export link in its reply, then verifies the automation successfully detects and downloads the real file to `02_vault/downloads/`.

## Processing Logic

Builds a [[copilot_ask|CopilotBridge]] instance with `download_dir` pointed at `02_vault/downloads/`, then calls `.ask(prompt_text=..., expect_file_download=True, timeout=180)`. The prompt deliberately asks Copilot to include a download/export link in its answer, since that's what the automation's link-scoring logic (see [[copilot_ask]]) looks for and clicks.

## Output

Console: Copilot's response text, then either the saved file's local path or a failure message if no file was captured.

## Notes for AI reuse

This is the reference example for exercising [[copilot_ask]]'s SharePoint/OneDrive direct-download-link rewriting logic end to end. If file-download support is ever ported into the production adapter ([[copilot_bridge]]), this script's prompt wording (explicitly requesting a download link) is required for the automation to have something to click -- Copilot won't offer a download control unless asked to.
