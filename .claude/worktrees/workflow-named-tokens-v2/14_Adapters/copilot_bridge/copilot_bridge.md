---
tool_id: 'copilot_bridge'
title: 'M365 Copilot Bridge'
classification: '00_System_Core/adapters'
data_policy: 'internal'
execution_engine: 'browser_automation'
tags: [type/module, domain/system-core, tier/zero-input, function/browser-automation, scope/m365-copilot, connects/core-router, connects/server, connects/workflow-engine]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# copilot-bridge

> **Status:** Active. Production adapter -- not run interactively day-to-day; dispatched by [[core_router]] via `/execute/05_Processes/copilot_bridge` whenever [[server]] or [[workflow_engine]] needs a Copilot answer, image, or agent chat. Can also be run by hand from a terminal for testing (see Actions below).

## Purpose

Lets the rest of Workbrain ask Microsoft 365 Copilot questions, generate images (via Copilot's Designer plugin), and chat with specific named Copilot agents (via "@agent" mentions) -- all by remote-controlling a real, normally-invisible copy of Microsoft Edge through the [[gemini_bridge|same general approach as the Gemini bridge]], except Copilot has no equivalent of `gemini_webapi`'s cookie+HTTP shortcut, so every action here drives the actual chat web page directly: type into the box, submit, wait for the answer to settle on screen, read it back out. No API key anywhere -- authentication rides entirely on the signed-in Edge profile at `copilot_browser_profile/`.

## Processing Logic

### One-time setup: `initialize_edge_profile()`

Opens a **visible** Edge window at `https://m365.cloud.microsoft/chat/` for 3 minutes so a human can complete the organization's normal M365 SSO login once. Every other function in this file reuses that saved session headlessly afterward. Re-run via `{"action": "init"}` if a later call fails to find the chat UI logged in.

### Shared helpers

* `_launch_context(p, headless)` -- clears any stale `SingletonLock` first (`purge_browser_profile_locks()`), then opens Edge against `copilot_browser_profile/`.
* `_submit_prompt(page, prompt_text)` -- types the prompt into the compose box and submits it (click Send, or press Enter as a fallback). Includes a fixed 2.5s settle delay after the box becomes visible -- typing immediately after `wait_for(state="visible")` was found to get silently dropped, since the chat app isn't fully interactive the instant the box renders.
* `_await_response(page, prompt_text, timeout=75)` -- polls the visible answer text once a second until it stops growing for 4 consecutive checks and isn't one of Copilot's known "searching/thinking" placeholder phrases (`is_preliminary_response`). Falls back to scraping the whole page body if no recognized container ever settles.
* `_iter_mention_agents(page)` / `_select_agent_mention(page, agent_name)` -- drive the "@" mention picker (see below).

### Actions (JSON payload, positional CLI arg)

Always prints exactly one JSON line to stdout: `{"success": true, ...}` or `{"success": false, "response": "<error>"}` (non-zero exit code on failure).

* **`init`** -- the one-time sign-in flow above.
* **`ask`** -- plain question via `ask_copilot(prompt_text)`. Returns `{"success": true, "response": "..."}`.
* **`generate_image`** -- asks Copilot's Designer plugin to generate an image. Copilot renders the result inline as a base64 `data:image/...` URI (`<img alt="... Image">`), so this decodes and writes it straight to `output_dir` (default `02_vault/generated_images`) with no download step. Returns `{"success": true, "file_path": "..."}`. Designer appears to have its own per-day/session rate limit -- once hit, Copilot answers with empty/plain text instead of an image; this is surfaced as a clear error message rather than a raw Playwright timeout.
* **`list_agents`** -- opens the chat's "@" mention picker and returns every real agent available to ground a message to: `{"success": true, "agents": [{"name": "Hal-9000", "description": "..."}, ...]}`. Matches exactly what `ask_agent` can target.
* **`ask_agent`** -- types `"@" + agent` into the compose box, selects the matching entry (exact name preferred, falls back to substring), which inserts a **grounding chip** into the compose box (does not navigate away or open a separate thread), then submits the real prompt and scrapes the response the same way `ask` does. Returns `{"success": true, "response": "..."}`.

### How the "@" agent mention works

Typing `@` opens a `role="menu"` popup listing every agent pinned/available to the signed-in user (each `role="menuitem"` has an avatar `aria-label` equal to the agent's display name, plus a short description via `span.fai-BebopGroundingMenuItem__secondaryText`). A pseudo-entry named "Get agents" (a link to the full Agent Store) is filtered out via `NON_AGENT_MENTION_LABELS`. `list_agents` and `ask_agent` both drive this exact picker; there is no separate "agent directory" API involved.

### Legacy CLI compatibility

`main()` also accepts the older `--prompt` / `--input` / `--output` / `--template` flag style (predates the JSON-action contract). `--input` falls back to `synthesize_db_fallback_context()` -- a small text summary pulled straight from [[database|brain_state.db]] -- if the given file path doesn't exist.

## Output

One JSON line on stdout per invocation (see Actions above). Non-zero exit code whenever `"success": false`.

## Notes for AI reuse

* Every browser launch goes through `_launch_context`/`_chrome_switches` -- if you add a new action, reuse those rather than hand-rolling another `launch_persistent_context` call, so lock-cleanup and headless flags stay consistent.
* If a new action ever needs to wait on the compose box right after `page.goto(NAV_URL)`, copy the 2.5s settle delay pattern from `_submit_prompt`/`_select_agent_mention` -- skipping it reproduces the "typed text silently vanishes" bug documented inline in the code.
* See [[gemini_bridge]] for the equivalent Gemini-side adapter (same action contract shape, different underlying mechanism), [[core_router]] for how this gets dispatched, and [[workflow_engine]] for the Workflow Builder nodes (`function_copilot_image_generate`, `function_copilot_agent_ask`, `function_copilot_list_agents`, `builtin_ai_processor`) that call into this file.

## Required dependencies

Already covered by `requirements.txt`: `playwright` only. No `.env` entry, no API key.
