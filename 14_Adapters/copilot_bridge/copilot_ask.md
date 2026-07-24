---
tool_id: 'copilot_ask'
title: 'Copilot Ask (Legacy CopilotBridge Class)'
classification: '00_System_Core/adapters'
data_policy: 'internal'
execution_engine: 'browser_automation'
tags: [type/module, domain/system-core, tier/zero-input, function/browser-automation, scope/m365-copilot, connects/copilot-bridge]
---

# copilot-ask

> **Status:** Experimental / not wired into Cortex. An earlier, class-based prototype of the Copilot automation engine -- not imported by [[core_router]], [[server]], or [[workflow_engine]]. Only the manual test scripts in this same folder ([[run_copilot_test]], [[run_copilot_download_test]], [[copilot_prompt_engineer]]) use it.

## Purpose

Prototype `CopilotBridge` class exploring two features the production adapter ([[copilot_bridge]]) doesn't currently have: attaching a local file to a Copilot question (so it can read/summarize a document), and detecting + downloading a file Copilot generates in its reply (e.g. asking it to produce a Word document and pulling the real file back down to disk). Everything else -- launching Edge, typing a question, waiting for the streamed answer to settle, cleaning UI clutter out of the scraped text -- works the same general way as [[copilot_bridge]].

## Processing Logic

### `CopilotBridge.__init__(profile_name="default", headless=True, download_dir=None)`

`profile_name` lets more than one instance run concurrently without fighting over the same saved-login folder -- each non-default name gets its own `copilot_browser_profile_<name>/` folder.

### `CopilotBridge.ask(prompt_text="", target_url="", file_to_upload=None, expect_file_download=False, custom_download_dir=None, timeout=180) -> {"text", "downloaded_file"}`

The one method that does everything: optionally attaches `file_to_upload` via the page's (usually hidden) `input[type='file']` element, fills and submits the prompt (or navigates straight to a pre-built `target_url` if one was given -- see [[copilot_prompt_engineer]]), waits for the answer to settle using the same stabilize-then-confirm polling approach as [[copilot_bridge]], and -- if `expect_file_download=True` -- scores every link/button in the latest answer block to find the most likely "download this file" control (highest score: text containing both an action word like "download" and a file extension like ".docx"), rewrites SharePoint/OneDrive viewer links into direct-download endpoints via `_make_sharepoint_direct_download`, and captures the resulting download via Playwright's `expect_download()`.

### `ask_copilot(...)` (module-level function)

A thin backward-compatible wrapper: creates a one-off `CopilotBridge` and calls `.ask(...)` on it, for scripts written before the class existed.

## Output

`{"text": "<cleaned response>", "downloaded_file": "<path or None>"}` from `.ask(...)`.

## Notes for AI reuse

If the file-upload or file-download capability is ever needed in production, port the relevant logic from `.ask()` here into [[copilot_bridge]]'s action-based contract (add `"action": "ask_with_file"` / `expect_file_download` support there) rather than wiring this prototype class into [[core_router]] directly -- keeps exactly one production Copilot adapter with one JSON contract, consistent with how [[gemini_bridge]] is structured.
