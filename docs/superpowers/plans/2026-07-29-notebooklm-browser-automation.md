# NotebookLM Browser Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When `NOTEBOOKLM_MOCK_MODE=0`, `notebooklm_bridge.py`'s 4 actions (`create_notebook`, `upload_sources`, `ask`, `prompt_loop`) drive a real, persistent-profile Playwright browser session against `notebooklm.google.com` instead of raising "not configured," returning the exact same JSON shape mock mode already does.

**Architecture:** Mirrors `copilot_bridge.py`'s established shape exactly: a persistent Chromium/Edge profile (one-time headed login via a new `init` action), headless automated calls afterward, and a `_await_..._response` polling loop copied from `copilot_bridge._await_response` for reading a streamed AI answer off the page. `MOCK_MODE` (unchanged env toggle) picks mock vs. real per call; nothing outside this one file changes.

**Tech Stack:** Python 3, `playwright.sync_api` (already in `requirements.txt`, no new dependency), Microsoft Edge (`channel="msedge"`).

## Global Constraints

- Real mode must return the **exact same JSON shape** as mock mode for all 4 actions — this is what keeps `workflow_engine.py` and the 3 standalone Tasks unchanged.
- No new Python dependencies.
- `headless` defaults to `True` for all 4 automated actions (per the spec's explicit ask to explore whether headless works); `init` is always headed (it's the interactive login step).
- Match `copilot_bridge.py`'s/`gemini_bridge.py`'s existing code conventions in this file: comments explain *why*, one JSON line to stdout, catch-all `try/except` in `main()`.

**Correction versus the spec doc:** the spec said the new profile folder should live "outside the watched code tree, matching copilot_bridge/abc_uploader." Checking `server.py`'s actual `uvicorn.run(..., reload_excludes=[...])` (around line 1611) shows `*/14_Adapters/*` is already blanket-excluded from the reload watcher — which is *why* `copilot_bridge.py`'s own profile safely lives right next to it at `14_Adapters/copilot_bridge/copilot_browser_profile/` (confirmed by reading `copilot_bridge.py` directly: `USER_DATA_DIR = SCRIPT_PATH.parent / "copilot_browser_profile"`). Only `abc_uploader` (which lives in `12_Tasks/`, also blanket-excluded) additionally happens to sit at the vault root. Since `notebooklm_bridge.py` already lives inside `14_Adapters/`, the simpler, more common pattern (2 of 3 existing adapters) is to put the profile right next to the file — that's what this plan does. The reload-safety property is identical either way; this is purely about matching the more common convention.

---

### Task 1: Real browser automation in `notebooklm_bridge.py`

**Files:**
- Modify: `14_Adapters/notebooklm_bridge/notebooklm_bridge.py`
- Modify: `14_Adapters/notebooklm_bridge/test_notebooklm_bridge.py`
- Modify: `14_Adapters/notebooklm_bridge/notebooklm_bridge.md`
- Modify: `.gitignore`
- Modify: `00_System/server.py:1611-1629` (`reload_excludes` list)

**Interfaces:**
- Produces: `create_notebook(title, headless=True)`, `upload_sources(notebook_id, file_paths, headless=True)`, `ask(notebook_id, prompt, headless=True)`, `prompt_loop(notebook_id, prompts, headless=True)` — same names as today, each gaining a `headless` keyword arg with a default, so every existing caller (the 3 standalone Tasks, `workflow_engine.py`) keeps working with zero changes.
- Consumes: nothing from other tasks — this NotebookLM plan and the separate Named Tokens plan are independent (per both specs).

- [ ] **Step 1: Remove the now-invalid mock-mode-off test first**

`test_notebooklm_bridge.py`'s `test_mock_mode_off_fails_clearly` currently asserts that `MOCK_MODE=False` makes `create_notebook` raise `RuntimeError("...not configured...")`. Once this task lands, `MOCK_MODE=False` means "really launch a browser" instead — that assertion becomes false, and worse, running it in an environment with no Edge/no display would hang or error unpredictably. Remove it now, before writing the real-mode code, so there's no window where the test suite is red for the wrong reason.

In `14_Adapters/notebooklm_bridge/test_notebooklm_bridge.py`, delete the `test_mock_mode_off_fails_clearly` function (lines 51-60) and its call in `__main__` (line 60 area):

```python
def test_prompt_loop_asks_each_prompt_in_order():
    prompts = ["What is Period 1 about?", "What is Period 2 about?"]
    result = nb.prompt_loop("nb_test", prompts)
    assert len(result["qa_pairs"]) == 2
    assert result["qa_pairs"][0]["prompt"] == prompts[0]
    assert result["qa_pairs"][1]["prompt"] == prompts[1]
    assert "nb_test" in result["qa_pairs"][0]["response"]


if __name__ == "__main__":
    test_create_notebook_returns_notebook_id()
    test_upload_sources_validates_real_files()
    test_upload_sources_requires_notebook_id()
    test_prompt_loop_asks_each_prompt_in_order()
    print("All notebooklm_bridge self-checks passed.")
```

(Real/browser mode isn't unit-testable — no live Google login in an automated test run — so it's covered by the manual smoke test in Step 6 instead, not a new automated test. This matches what the approved spec's "Testing" section already says.)

- [ ] **Step 2: Run the trimmed test file to confirm it's still green**

Run: `python 14_Adapters/notebooklm_bridge/test_notebooklm_bridge.py`
Expected: `All notebooklm_bridge self-checks passed.`

- [ ] **Step 3: Update the module docstring**

In `14_Adapters/notebooklm_bridge/notebooklm_bridge.py`, replace the header comment block (lines 1-33) with:

```python
# =============================================================================
# notebooklm_bridge.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   Adapter for Google NotebookLM: create a notebook, upload sources
#   (PDF/Docx/JSON files), and ask it a sequence of questions. There is no
#   live Gemini Enterprise/NotebookLM API or MCP access wired up yet, so by
#   default every action runs in MOCK_MODE -- it returns realistic-shaped
#   fake data instead of talking to a real service. With MOCK_MODE off, this
#   file instead drives a real, invisible copy of Microsoft Edge against
#   notebooklm.google.com -- the same interim approach copilot_bridge.py and
#   abc_uploader.py already use for other Google/Microsoft products with no
#   official API. The action names, parameters, and response shape are the
#   real contract in both modes; swapping in a real Enterprise API/MCP call
#   later only touches this file's real-mode internals.
#
# WHAT IT INTERACTS WITH
#   - `core_router.py`, which is what actually runs this file when
#     `workflow_engine.py`'s NotebookLM function nodes dispatch to it (same
#     mechanism gemini_bridge.py/copilot_bridge.py use).
#   - Microsoft Edge, automated via the "Playwright" library, when MOCK_MODE
#     is off -- opening notebooklm.google.com, clicking/typing/reading the
#     page exactly like a person would. No API key is used anywhere.
#   - A folder named `notebooklm_browser_profile` (right next to this file),
#     which holds the saved Google login after the one-time `init` action.
#     Deleting it forces signing in again.
#
# KEY FUNCTIONALITY NOTES
#   - Every action is triggered by a small JSON instruction, e.g.
#     {"action": "create_notebook", "title": "..."}. This file always prints
#     back exactly one line of JSON describing what happened -- the same
#     "contract" gemini_bridge.py/copilot_bridge.py use.
#   - MOCK_MODE (env var NOTEBOOKLM_MOCK_MODE, default on) is a separate
#     concern from workflow_engine.py's own dry_run: dry_run means "don't
#     call any adapter at all yet", while MOCK_MODE means "use simulated
#     responses instead of driving a real browser."
#   - upload_sources still validates that every given file path is a real
#     file on disk in BOTH modes -- a real usage mistake (typo'd path)
#     should surface immediately rather than being hidden behind the mock,
#     and a real upload would fail on a bad path anyway.
#   - Selectors for NotebookLM's "New notebook" button, "Add source" button,
#     chat box, and response area are unverified best-effort guesses (same
#     caveat abc_uploader.md's Known Limitations section carries) -- see
#     notebooklm_bridge.md for what to check if real mode stops working.
# =============================================================================
```

- [ ] **Step 4: Add browser-automation imports, constants, and shared helpers**

Replace the current imports/constants block (lines 35-52) with:

```python
# 14_Adapters/notebooklm_bridge/notebooklm_bridge.py
import sys
sys.dont_write_bytecode = True

import os
import re
import time
import json
import uuid
import argparse
from pathlib import Path
from typing import Any, Dict, List

from playwright.sync_api import sync_playwright

MOCK_MODE = os.environ.get("NOTEBOOKLM_MOCK_MODE", "1") != "0"

SCRIPT_PATH = Path(__file__).resolve()
NOTEBOOKLM_URL = "https://notebooklm.google.com"

# Right next to this file, same placement as copilot_bridge.py's/gemini_bridge.py's
# own profiles -- already covered by server.py's reload_excludes ("*/14_Adapters/*"),
# so it's safe here without needing the vault-root workaround abc_uploader.py uses.
USER_DATA_DIR = SCRIPT_PATH.parent / "notebooklm_browser_profile"
USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Best-effort, unverified selector guesses -- see notebooklm_bridge.md's Known
# Limitations for what to check first if any of these stop matching.
NEW_NOTEBOOK_SELECTORS = [
    "button:has-text('New notebook')",
    "button:has-text('Create new')",
    "[aria-label*='New notebook']",
]
RENAME_SELECTORS = [
    "[aria-label*='Notebook name']",
    "input[aria-label*='title']",
    ".notebook-title",
]
ADD_SOURCE_SELECTORS = [
    "button:has-text('Add source')",
    "button:has-text('Add sources')",
]
FILE_INPUT_SELECTORS = [
    "input[type='file']",
]
SOURCE_LOADING_SELECTORS = "[aria-label*='Loading'], .loading-spinner, [role='progressbar']"
CHAT_INPUT_SELECTORS = [
    "textarea[placeholder*='Ask']",
    "[role='textbox']",
    "textarea",
]
RESPONSE_SELECTORS = [
    "[data-testid='chat-message']",
    ".chat-message",
    "[role='article']",
    ".message-content",
]


def _find_selector(page, selectors: List[str]):
    """Returns the first matching, present locator out of a list of candidate
    selectors, or None -- same helper abc_uploader.py uses for the same reason
    (a product's DOM structure isn't guaranteed, so try several guesses)."""
    for selector in selectors:
        try:
            locator = page.locator(selector)
            if locator.count() > 0:
                return locator.first
        except Exception:
            continue
    return None


def purge_browser_profile_locks() -> None:
    """Clears a stale SingletonLock left behind by a previous run that didn't
    shut down cleanly -- same hardening as gemini_bridge.py/copilot_bridge.py."""
    lock_file = USER_DATA_DIR / "SingletonLock"
    if not lock_file.exists():
        return
    try:
        lock_file.unlink()
        print("[CLEANUP] Successfully unlinked stale browser profile SingletonLock handles.")
    except PermissionError:
        print("[WARNING] Active browser file lock detected. Orphaned background processes may be running.")
        if sys.platform == "win32":
            print("[CLEANUP] Dispatching taskkill to prune orphaned background edge driver assets...")
            os.system("taskkill /f /im msedge.exe /fi \"memusage lt 40000\" >nul 2>&1")
            time.sleep(1)
            try:
                lock_file.unlink()
            except Exception:
                pass
    except Exception:
        pass


def initialize_browser_profile() -> None:
    """One-time interactive login: opens a headed window to notebooklm.google.com
    so the user can complete Google SSO once. The resulting session persists in
    USER_DATA_DIR for every later headless call to reuse -- mirrors
    gemini_bridge.initialize_edge_profile / copilot_bridge.initialize_edge_profile."""
    print("[INIT] Launching headed browser for NotebookLM authentication...")
    print(f"[PATH] Session profile directory: {USER_DATA_DIR}")

    purge_browser_profile_locks()

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA_DIR),
            channel="msedge",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.new_page()
        page.goto(NOTEBOOKLM_URL)

        print("\n==================================================")
        print("[ACTION REQUIRED] Sign in to your Google account in the")
        print("newly opened Edge window now. This session will remain")
        print("open for 3 minutes. Once the NotebookLM home page loads")
        print("completely, you can close the window or wait for the timeout.")
        print("==================================================\n")

        try:
            for _ in range(180):
                if page.is_closed():
                    break
                time.sleep(1)
        except Exception:
            pass

        context.close()
        print("[SUCCESS] NotebookLM authentication session profile initialized.")


def _chrome_switches(headless: bool) -> List[str]:
    """Same low-level Edge/Chromium startup flags copilot_bridge.py uses for
    unattended automation."""
    switches = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--mute-audio",
        "--no-first-run",
        "--disable-extensions",
    ]
    if headless:
        switches.extend(["--headless=new", "--disable-gpu", "--disable-software-rasterizer"])
    return switches


def _launch_context(p, headless: bool):
    """Shared launch helper for every real action below."""
    purge_browser_profile_locks()
    return p.chromium.launch_persistent_context(
        user_data_dir=str(USER_DATA_DIR),
        channel="msedge",
        headless=headless,
        args=_chrome_switches(headless),
    )
```

(Drop the old `NOT_CONFIGURED_MESSAGE` constant entirely -- it's dead now that "not mock" means "drive a real browser" instead of raising it.)

- [ ] **Step 5: Add the real per-action implementations**

Add these functions after the helpers from Step 4, before the existing `create_notebook`/`upload_sources`/`ask`/`prompt_loop` functions:

```python
def _await_notebooklm_response(page, prompt_text: str, timeout: int = 90) -> str:
    """Polls the chat pane for a settled response and returns its text -- same
    stable-length polling strategy as copilot_bridge._await_response, adapted
    to NotebookLM's (unverified-guess) selectors."""
    start_time = time.time()
    last_length = 0
    stable_count = 0
    final_response = ""

    while time.time() - start_time < timeout:
        current_text = ""
        for selector in RESPONSE_SELECTORS:
            try:
                loc = page.locator(selector)
                if loc.count() > 0:
                    current_text = loc.last.text_content()
                    if current_text and len(current_text.strip()) > 10:
                        break
            except Exception:
                pass

        current_text_clean = current_text.strip() if current_text else ""
        current_length = len(current_text_clean)

        if current_length > 0 and current_length == last_length:
            stable_count += 1
            if stable_count >= 4:
                final_response = current_text_clean
                break
        else:
            stable_count = 0
            last_length = current_length

        time.sleep(1)

    if not final_response:
        try:
            page_text = page.locator("body").text_content()
            final_response = (
                page_text.split(prompt_text)[-1].strip()
                if prompt_text in page_text
                else page_text[-1500:].strip()
            )
        except Exception as e:
            final_response = f"Failed fallback scrape: {e}"

    return final_response


def _browser_ask_in_page(page, prompt: str) -> str:
    """Types+submits one prompt into an already-open notebook page and waits
    for the answer. Shared by _browser_ask (one question) and
    _browser_prompt_loop (many, same page/session)."""
    chat_box = _find_selector(page, CHAT_INPUT_SELECTORS)
    if not chat_box:
        raise RuntimeError("Could not locate the NotebookLM chat input box.")
    chat_box.click()
    chat_box.fill(prompt)
    page.wait_for_timeout(500)
    chat_box.press("Enter")
    return _await_notebooklm_response(page, prompt)


def _browser_create_notebook(title: str, headless: bool) -> Dict[str, Any]:
    with sync_playwright() as p:
        context = _launch_context(p, headless)
        try:
            page = context.new_page()
            page.goto(NOTEBOOKLM_URL)
            page.wait_for_timeout(2000)

            new_btn = _find_selector(page, NEW_NOTEBOOK_SELECTORS)
            if not new_btn:
                raise RuntimeError("Could not locate a 'New notebook' button on the NotebookLM home page.")
            new_btn.click()
            page.wait_for_timeout(2000)
            try:
                page.wait_for_url("**/notebook/**", timeout=15000)
            except Exception:
                pass

            match = re.search(r"/notebook/([a-zA-Z0-9\-]+)", page.url)
            if not match:
                raise RuntimeError(f"Notebook created but no notebook id could be read from the URL: {page.url}")
            notebook_id = match.group(1)

            if title:
                rename_field = _find_selector(page, RENAME_SELECTORS)
                if rename_field:
                    try:
                        rename_field.click()
                        rename_field.fill(title)
                        page.keyboard.press("Enter")
                    except Exception:
                        pass

            return {"notebook_id": notebook_id, "title": title}
        finally:
            context.close()


def _browser_upload_sources(notebook_id: str, file_paths: List[str], headless: bool) -> Dict[str, Any]:
    with sync_playwright() as p:
        context = _launch_context(p, headless)
        try:
            page = context.new_page()
            page.goto(f"{NOTEBOOKLM_URL}/notebook/{notebook_id}")
            page.wait_for_timeout(2000)

            add_btn = _find_selector(page, ADD_SOURCE_SELECTORS)
            if add_btn:
                add_btn.click()
                page.wait_for_timeout(1000)

            file_input = _find_selector(page, FILE_INPUT_SELECTORS)
            if not file_input:
                try:
                    page.wait_for_selector("input[type='file']", timeout=5000)
                except Exception:
                    pass
                file_input = _find_selector(page, FILE_INPUT_SELECTORS)
            if not file_input:
                raise RuntimeError("Could not locate a file input on the notebook page to upload sources.")

            file_input.set_input_files(file_paths)
            try:
                page.wait_for_selector(SOURCE_LOADING_SELECTORS, state="hidden", timeout=60000)
            except Exception:
                pass

            return {
                "sources": [
                    {"source_id": f"src_{uuid.uuid4().hex[:12]}", "filename": Path(p).name, "status": "processed"}
                    for p in file_paths
                ]
            }
        finally:
            context.close()


def _browser_ask(notebook_id: str, prompt: str, headless: bool) -> Dict[str, Any]:
    with sync_playwright() as p:
        context = _launch_context(p, headless)
        try:
            page = context.new_page()
            page.goto(f"{NOTEBOOKLM_URL}/notebook/{notebook_id}")
            page.wait_for_timeout(2000)
            return {"response": _browser_ask_in_page(page, prompt)}
        finally:
            context.close()


def _browser_prompt_loop(notebook_id: str, prompts: List[str], headless: bool) -> Dict[str, Any]:
    with sync_playwright() as p:
        context = _launch_context(p, headless)
        try:
            page = context.new_page()
            page.goto(f"{NOTEBOOKLM_URL}/notebook/{notebook_id}")
            page.wait_for_timeout(2000)
            qa_pairs = [{"prompt": p_text, "response": _browser_ask_in_page(page, p_text)} for p_text in prompts]
            return {"qa_pairs": qa_pairs}
        finally:
            context.close()
```

- [ ] **Step 6: Wire the public functions to dispatch mock vs. real, add `headless`**

Replace the 4 existing public functions (current lines 55-99) with:

```python
def create_notebook(title: str, headless: bool = True) -> Dict[str, Any]:
    if MOCK_MODE:
        return {"notebook_id": f"nb_{uuid.uuid4().hex[:12]}", "title": title}
    return _browser_create_notebook(title, headless)


def upload_sources(notebook_id: str, file_paths: List[str], headless: bool = True) -> Dict[str, Any]:
    if not notebook_id:
        raise ValueError("upload_sources requires a notebook_id.")
    for raw_path in file_paths:
        if not Path(raw_path).exists():
            raise FileNotFoundError(f"Source file not found: {raw_path}")

    if MOCK_MODE:
        return {
            "sources": [
                {"source_id": f"src_{uuid.uuid4().hex[:12]}", "filename": Path(p).name, "status": "processed"}
                for p in file_paths
            ]
        }
    return _browser_upload_sources(notebook_id, file_paths, headless)


def ask(notebook_id: str, prompt: str, headless: bool = True) -> Dict[str, Any]:
    if not notebook_id:
        raise ValueError("ask requires a notebook_id.")
    if MOCK_MODE:
        return {"response": f"[MOCK NotebookLM response for notebook {notebook_id}] {prompt[:300]}"}
    return _browser_ask(notebook_id, prompt, headless)


def prompt_loop(notebook_id: str, prompts: List[str], headless: bool = True) -> Dict[str, Any]:
    if not notebook_id:
        raise ValueError("prompt_loop requires a notebook_id.")
    if MOCK_MODE:
        qa_pairs = [{"prompt": p, "response": ask(notebook_id, p)["response"]} for p in prompts]
        return {"qa_pairs": qa_pairs}
    return _browser_prompt_loop(notebook_id, prompts, headless)
```

(Note: the file-existence check in `upload_sources` moved out of the mock-only branch to the top of the function, since it should apply in both modes — matches the docstring update in Step 3.)

- [ ] **Step 7: Wire `init` action and `headless` param into `main()`**

Replace the body of `main()` from `action = params.get("action", "")` down through the `try/except` (current lines 124-142) with:

```python
    action = params.get("action", "")
    headless = bool(params.get("headless", True))

    try:
        if action == "init":
            initialize_browser_profile()
            result = {"success": True, "response": "NotebookLM authentication session profile initialized."}
        elif action == "create_notebook":
            result = {"success": True, **create_notebook(params.get("title", "Untitled Notebook"), headless=headless)}
        elif action == "upload_sources":
            result = {"success": True, **upload_sources(params.get("notebook_id", ""), params.get("file_paths", []), headless=headless)}
        elif action == "ask":
            result = {"success": True, **ask(params.get("notebook_id", ""), params.get("prompt", ""), headless=headless)}
        elif action == "prompt_loop":
            result = {"success": True, **prompt_loop(params.get("notebook_id", ""), params.get("prompts", []), headless=headless)}
        else:
            result = {"success": False, "response": f"Unknown action: {action}"}
    except Exception as e:
        # Catch absolutely everything here rather than letting the script
        # crash with a raw Python error -- the caller (core_router.py,
        # workflow_engine.py) expects a clean JSON line back no matter what
        # went wrong.
        result = {"success": False, "response": f"NotebookLM bridge error: {e}"}
```

Also update the one-line usage message a few lines above it (current lines 111-115) to mention `init`:

```python
    if not args.payload:
        print(json.dumps({
            "success": False,
            "response": 'No JSON payload provided. Expected: {"action": "init|create_notebook|upload_sources|ask|prompt_loop", ...}',
        }))
        sys.exit(1)
```

- [ ] **Step 8: Run the test file again**

Run: `python 14_Adapters/notebooklm_bridge/test_notebooklm_bridge.py`
Expected: `All notebooklm_bridge self-checks passed.` (mock mode is default and untouched by this task's real-mode additions).

- [ ] **Step 9: `.gitignore` and `server.py` reload-exclude entries**

In `.gitignore` (around line 90-92):

```
# Playwright persistent browser profiles (workbrain automation adapters)
abc_uploader_browser_profile/
gemini_browser_profile/
notebooklm_browser_profile/
```

In `00_System/server.py`'s `reload_excludes` list (around line 1611-1629), add one entry next to the other named profile exclusions:

```python
            reload_excludes=[
                "*.db",
                "*.pyc",
                "*__pycache__*",
                "*copilot_browser_profile*",
                "*abc_uploader_browser_profile*",
                "*notebooklm_browser_profile*",
                "*/11_Processes/*",
```

(Belt-and-suspenders: `*/14_Adapters/*` already covers this path, but every other named profile gets its own explicit entry too, so this stays consistent if that blanket rule ever narrows.)

- [ ] **Step 10: Update `notebooklm_bridge.md`**

Replace the file's `Status` line (line 13) and `MOCK_MODE` section (lines 26-32) with:

```markdown
> **Status:** Mock mode by default; real browser automation available via `NOTEBOOKLM_MOCK_MODE=0` as an interim step while proper Gemini Enterprise/NotebookLM API or MCP access is pursued (see Real Mode below). There is still no public API/MCP access for Google NotebookLM as of this writing (see [[gemini_bridge]]'s own note on this).
```

```markdown
### `MOCK_MODE` (env var `NOTEBOOKLM_MOCK_MODE`, default on)

A separate concern from `workflow_engine.py`'s own `dry_run`: `dry_run`
means "don't call any adapter at all yet"; `MOCK_MODE` means "simulate a
backend" vs. "drive a real browser." With `MOCK_MODE` off, every action
launches a real, persistent-profile Playwright session against
`notebooklm.google.com` -- see Real Mode below.
```

Add a new section after "Actions (JSON payload, positional CLI arg)" (after line 52, before `## Output`):

```markdown
### Real Mode (`NOTEBOOKLM_MOCK_MODE=0`)

Interim step toward proper Enterprise API/MCP access -- same persistent-profile
browser automation pattern as [[copilot_bridge]] and `abc_uploader`, since no
maintained unofficial API library exists for NotebookLM (unlike
[[gemini_bridge]], which hands session cookies to the third-party
`gemini_webapi` library).

* **One-time setup:** run `python notebooklm_bridge.py '{"action": "init"}'`
  (or trigger it from wherever `init` is exposed in the Cortex UI, if wired
  up there). Opens a headed Edge window to `notebooklm.google.com` for you to
  sign into Google once; the session is saved to
  `notebooklm_browser_profile/` (git-ignored, right next to this file) and
  reused by every later automated call.
* **`headless`** (optional, default `true` on every action payload) -- set to
  `false` to watch the automation run, useful while verifying selectors.
* All 4 actions return the **same JSON shape** in real mode as in mock mode.
* `notebook_id` in real mode is the notebook's ID segment read out of its
  NotebookLM URL (`notebooklm.google.com/notebook/<id>`), not a fabricated
  UUID.

#### Known Limitations

* Selectors for "New notebook," "Add source," the chat box, and the response
  area (`NEW_NOTEBOOK_SELECTORS`, `ADD_SOURCE_SELECTORS`,
  `CHAT_INPUT_SELECTORS`, `RESPONSE_SELECTORS` near the top of
  `notebooklm_bridge.py`) are unverified best-effort guesses -- same caveat
  `abc_uploader.md`'s Known Limitations section carries. If real mode stops
  finding a button/field it used to, inspect the live page and update the
  matching selector list.
* Headless is the default, but Google surfaces sometimes behave differently,
  or add extra verification challenges, under headless automation. Pass
  `"headless": false` in the action payload if a call that works headed
  fails headless.
* This remains an interim step. Swapping in a real Gemini Enterprise/
  NotebookLM API or MCP call later is a self-contained future change to this
  file's real-mode internals only.
```

- [ ] **Step 11: Manual live smoke test (you'll need to run this yourself — it needs your Google login)**

1. `python 14_Adapters/notebooklm_bridge/notebooklm_bridge.py '{"action": "init"}'` — sign into Google in the headed window that opens.
2. `python 14_Adapters/notebooklm_bridge/notebooklm_bridge.py "{\"action\": \"create_notebook\", \"title\": \"Smoke Test\", \"headless\": false}"` — watch it create a notebook; confirm the printed JSON has a real `notebook_id` matching the notebook's URL.
3. Using that `notebook_id`, run `upload_sources` with one small real local file, `ask` with a simple prompt, then `prompt_loop` with 2 prompts — confirm each returns real, non-mock text (not a Playwright exception) with `"headless": false` first; retry the same calls with `"headless": true` (or omitted) to see whether headless holds up, per the original "explore if headless works" goal.
4. If any step can't find a button/field, note which selector list needs updating per the Known Limitations section just added.

- [ ] **Step 12: Commit**

```bash
git add 14_Adapters/notebooklm_bridge/notebooklm_bridge.py 14_Adapters/notebooklm_bridge/test_notebooklm_bridge.py 14_Adapters/notebooklm_bridge/notebooklm_bridge.md .gitignore 00_System/server.py
git commit -m "$(cat <<'EOF'
Add real browser automation to notebooklm_bridge as an interim step

NOTEBOOKLM_MOCK_MODE=0 now drives a real, persistent-profile Playwright
session against notebooklm.google.com (same pattern as copilot_bridge/
abc_uploader) instead of failing with "not configured". Mock mode and the
JSON contract are unchanged, so nothing downstream needs to change.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```
