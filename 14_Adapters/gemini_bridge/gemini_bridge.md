---
tool_id: 'gemini_bridge'
title: 'Gemini Bridge'
classification: '00_System_Core/adapters'
data_policy: 'internal'
execution_engine: 'browser_automation'
tags: [type/module, domain/system-core, tier/zero-input, function/browser-automation, scope/gemini, connects/core-router, connects/server, connects/workflow-engine]
---

# gemini-bridge

> **Status:** Active, with a known-flaky feature (Deep Research -- see below). Production adapter dispatched by [[core_router]] via `/execute/05_Processes/gemini_bridge` whenever [[server]] or [[workflow_engine]] needs a Gemini answer, research report, or image.

## Purpose

Lets the rest of Workbrain talk to Google Gemini (text answers, "Deep Research" multi-step reports, and AI-generated images) using the operator's own signed-in Google account -- no `GEMINI_API_KEY`, no Google AI Studio account. Unlike [[copilot_bridge]], this adapter only uses browser automation (Playwright) for a brief, one-time-per-call task: launching the saved Edge profile just long enough to read back two session cookies. Every actual Gemini call afterward goes through the `gemini_webapi` library talking directly to Google's servers over plain HTTP, using those cookies -- fast, and not dependent on Gemini's chat page layout staying stable.

## Processing Logic

### One-time setup: `initialize_edge_profile()`

Opens a **visible** Edge window at `https://gemini.google.com/app` for 3 minutes so a human can complete the organization's shared Google/Microsoft SSO login once. Session cookies persist in `gemini_browser_profile/` for every later headless call to reuse.

### `_get_session_cookies()`

Launches the saved profile headlessly just long enough to read back `__Secure-1PSID` / `__Secure-1PSIDTS`, then closes immediately. Raises a clear `RuntimeError` (telling the caller to run `init`) if no session cookie is found at all.

### `_run_deep_research(client, prompt, poll_interval=15.0, timeout=600.0)` -- workaround, not upstream behavior

The bundled `gemini_webapi` library's own `client.deep_research(...)` waits on `plan.research_id` to poll status, but direct inspection (2026-07-20) confirmed neither the plan-proposal nor the start-confirmation response from Gemini currently carries a parseable `research_id` -- both come back `None`, and the confirmation reply itself is an empty-text "immersive chip" widget rather than a normal candidate. That makes the library's own `wait_for_deep_research()` raise immediately. This function works around it by polling the chat directly via `fetch_latest_chat_response(plan.cid)` instead of the broken research_id/status RPC, waiting past the short "I'm working on it" placeholder until a real, substantial (>200 char) report replaces it.

**Known flakiness:** even with this workaround, `create_deep_research_plan()` itself has been observed to occasionally return an empty plan (no title/steps at all) -- this looks like intermittent variance in Gemini's own Deep Research response format rather than something fixable from this side. Treat Deep Research as best-effort; `ask`/`search`(non-deep-research)/`generate_image` have all been verified reliable.

### Actions (JSON payload, positional CLI arg)

Always prints exactly one JSON line to stdout: `{"success": true, ...}` or `{"success": false, "response": "<error>"}` (non-zero exit code on failure). `gemini_webapi`'s loguru logger is silenced at import time (`_loguru_logger.remove()`) so nothing but this one JSON line ever reaches stdout/stderr -- important because [[core_router]] concatenates captured stderr after stdout in the response it hands back, which would otherwise corrupt the JSON payload with trailing log lines.

* **`init`** -- the one-time sign-in flow above.
* **`ask`** -- plain text generation via `generate_content(...)`.
* **`search`** -- runs the prompt through Gemini's Deep Research agent instead of a single-turn answer (see flakiness note above).
* **`generate_image`** -- one image via Gemini's built-in image generation, saved to `output_dir` (default `02_vault/generated_images`), returns its file path.

## Output

One JSON line on stdout per invocation (see Actions above). Non-zero exit code whenever `"success": false`.

## Notes for AI reuse

* If Deep Research needs to be made reliable, the next step is investigating why `create_deep_research_plan()` sometimes gets an empty response -- likely needs a retry-with-backoff wrapper, or may be an account/quota-side limit rather than a code bug.
* See [[copilot_bridge]] for the equivalent Copilot-side adapter (same JSON action contract shape, different underlying mechanism), [[core_router]] for how this gets dispatched, and [[workflow_engine]] for the Workflow Builder nodes (`function_gemini_ask`, `function_google_search`, `function_image_generate`) that call into this file.

## Required dependencies

Already covered by `requirements.txt`: `playwright` (browser profile + cookie capture) and `gemini_webapi` (the actual Gemini calls). No `.env` entry, no API key.

## Not covered

There is no public API for NotebookLM as of this writing, so this bridge does not (and cannot) integrate with it -- only Gemini proper.
