# NotebookLM Real Browser Automation — Design Spec

**Date:** 2026-07-29
**Status:** Approved by user, ready for implementation plan

## Background

`14_Adapters/notebooklm_bridge/notebooklm_bridge.py` already implements 4
actions (`create_notebook`, `upload_sources`, `ask`, `prompt_loop`) in
mock-mode only, per the prior
`2026-07-22-notebooklm-adapter-design.md` decision — there is no live Google
Gemini Enterprise/NotebookLM API or MCP access wired up yet.

The user's end goal is proper enterprise API access (Gemini
Enterprise/NotebookLM via an official API or MCP connection). That requires
credentials/procurement outside this codebase's control and isn't something
this spec can build. In the meantime, the user wants to explore whether a
browser-session automation approach — the same shape already used by
`gemini_bridge`, `copilot_bridge`, and `abc_uploader` for other
no-official-API Google/Microsoft surfaces — can deliver similar
functionality as an interim step, specifically exploring whether it can run
**headless**.

This spec covers only the interim browser-automation path. Swapping in a
real Enterprise API/MCP call later is explicitly a separate, self-contained
future change to this same file's real-mode internals — nothing downstream
needs to change when that happens, because real mode returns the exact same
JSON shape mock mode already does.

## Approaches Considered

1. **Browser-session automation (chosen).** Drive a real, persistent
   Edge/Chromium profile against `notebooklm.google.com`, matching
   `copilot_bridge`/`abc_uploader`'s pattern of driving the visible page per
   action. Not `gemini_bridge`'s cookie-extraction shortcut — that only
   works because a maintained third-party library (`gemini_webapi`) has
   already reverse-engineered Gemini's internal RPC calls; no equivalent
   library exists for NotebookLM.
2. **Reverse-engineer NotebookLM's internal API ourselves.** Rejected — a
   much bigger, more fragile undertaking than driving the visible UI, and
   duplicates work a real Enterprise API will make moot anyway.
3. **Stay mock-only until Enterprise API access lands.** Rejected for now —
   doesn't answer the "can headless work in the meantime" question and
   blocks the exam-question pipeline indefinitely on procurement.

## Architecture

Everything stays inside `notebooklm_bridge.py`. The existing
`NOTEBOOKLM_MOCK_MODE` env toggle (default on) is unchanged in meaning; when
it's off, each action calls a new Playwright-backed implementation instead
of raising `NOT_CONFIGURED_MESSAGE`.

New persistent profile directory: `notebooklm_browser_profile/` at the vault
root — outside the watched code tree, matching `copilot_bridge`/
`abc_uploader`'s rationale (Playwright's constant cache/lock writes would
otherwise trip Uvicorn's `--reload` watcher if this is ever wired into a
live workflow run). Added to `.gitignore` alongside the other two browser
profile entries.

New `init` action (mirrors `gemini_bridge.initialize_edge_profile` /
`copilot_bridge`'s one-time sign-in flow): opens a headed window to
`https://notebooklm.google.com`, keeps it open up to 3 minutes for the user
to complete Google SSO login once, then closes. Every later automated call
reuses that saved session.

## Actions

All four keep the **exact same return shape** as mock mode today — this is
the property that keeps every downstream caller (the 3 standalone Tasks,
`workflow_engine.py`'s node dispatch) unchanged regardless of mock/real
mode.

* **`create_notebook(title)`** — headless by default (`headless` param,
  same convention as `abc_uploader`/`copilot_bridge`). Opens the profile,
  clicks "New notebook," renames it to `title` if a rename control is
  found (else keeps Google's auto-title), reads the notebook's ID out of
  its URL (`notebooklm.google.com/notebook/<id>`). Returns
  `{"notebook_id": ..., "title": ...}`.
* **`upload_sources(notebook_id, file_paths)`** — navigates to
  `.../notebook/<notebook_id>`, clicks "Add source," drives the file
  `<input type="file">` directly with the real local paths (simpler than
  `abc_uploader`'s in-memory-buffer approach, since these are already real
  files on disk), polls each source's processing indicator until it
  clears. Returns `{"sources": [...]}`.
* **`ask(notebook_id, prompt)`** — navigates to the notebook, types into
  the chat box, submits, polls for the response to finish generating using
  the same "candidate-selectors + full-visible-page-text fallback" pattern
  already proven in `copilot_bridge._await_response`. Returns
  `{"response": ...}`.
* **`prompt_loop(notebook_id, prompts)`** — one browser session/page,
  loops `ask()` per prompt in sequence (same structure the mock
  implementation already uses). Returns `{"qa_pairs": [...]}`.

All four keep raising a clear error (not a silent fake success) if any
Playwright step fails outright, caught by the existing `main()`
try/except.

No new action is needed for a "priming prompt" — it's just the first
`ask()` call, or the first item in `prompt_loop`'s `prompts` list.

## Integration

Zero changes needed to `workflow_engine.py`, the 3 standalone Tasks
(`create_notebooklm_notebook`, `upload_notebooklm_sources`,
`run_notebooklm_prompt_loop`), or `server.py` — they all call these 4
functions/CLI actions and only care about the JSON shape, which is
unchanged between mock and real mode.

Once the separate `2026-07-29-workflow-named-tokens-design.md` work lands,
a real pipeline can wire this adapter's outputs (e.g. a Create Notebook
node's `notebook_id`) into downstream nodes by name (e.g. `{Notebook}`)
instead of only via the raw `{{node_id}}` token — no change required here
for that to work.

## Known Limitations

* Selectors for "New notebook," "Add source," the chat box, and the
  "response ready" state are unverified best-effort guesses — the same
  caveat `abc_uploader.md`'s Known Limitations section already carries.
  They need one live headed smoke test (with the user's own Google login)
  to confirm/fix.
* Headless is the requested default, but Google surfaces commonly behave
  differently — or trigger extra verification challenges — under headless
  automation. The `headless` param is the escape hatch to headed if the
  smoke test shows problems.
* This adapter remains explicitly an interim step, not the end state.
  Swapping in a real Enterprise API/MCP call later only touches this file's
  real-mode internals.

## Testing

* Existing `test_notebooklm_bridge.py` already covers mock mode; no change
  needed there.
* Browser-mode automation is not covered by the automated test suite (a
  headless Google login can't run unattended in CI) — verification is the
  manual live smoke test described above.

## Explicitly Out of Scope

* Real Gemini Enterprise/NotebookLM API or MCP wiring (a later, separate,
  self-contained change to this file once credentials/access exist).
* Network drive retrieval, Red Seal scraping, dynamic prompt generation,
  and the end-to-end orchestration process — separate sub-projects from the
  same roadmap, each getting their own spec/plan cycle.
