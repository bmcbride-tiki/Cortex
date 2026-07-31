# =============================================================================
# gemini_bridge.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   This is the adapter that lets the rest of Workbrain talk to Google
#   Gemini (text answers, "Deep Research" reports, and AI-generated images)
#   using your own signed-in Google account -- no Gemini API key, no Google
#   AI Studio account, nothing to pay for or manage separately. It works by
#   borrowing your browser's login the same way a human using Gemini's
#   website would be logged in.
#
# WHAT IT INTERACTS WITH
#   - Microsoft Edge, automated via the "Playwright" library -- but ONLY to
#     sign you in once and to read back your login cookies afterward. It
#     does NOT use Edge to actually send questions to Gemini or read
#     answers back; see "KEY FUNCTIONALITY NOTES" below for why.
#   - The `gemini_webapi` library, a third-party Python package that speaks
#     to Gemini directly over the web (like a very targeted, private version
#     of what your browser does), using the login cookies this file hands
#     it. This is what actually sends prompts and receives answers.
#   - A folder named `gemini_browser_profile` (right next to this file),
#     which holds your saved Gemini login. Deleting it forces you to sign
#     in again.
#   - `core_router.py`, which is what actually runs this file when the
#     Cortex web app or the Workflow Builder asks for a Gemini action --
#     you don't normally run this file directly yourself.
#   - `02_vault/generated_images/`, where AI-generated images get saved by
#     default.
#
# KEY FUNCTIONALITY NOTES
#   - Two-stage login trick: most of the other AI adapters in this project
#     (e.g. copilot_bridge.py) drive a real, visible browser for every
#     single question, reading the answer directly off the web page. This
#     file only does that once, briefly, to capture two small pieces of
#     text called "session cookies" (basically a temporary keycard proving
#     you're logged in). After that, every question/answer goes through
#     `gemini_webapi` talking directly to Google's servers over plain web
#     requests -- much faster, and not dependent on Gemini's website layout
#     staying visually the same over time.
#   - Every action this file can perform (see `main()` near the bottom) is
#     triggered by a small JSON instruction, e.g.
#     {"action": "ask", "prompt": "..."}. This file always prints back
#     exactly one line of JSON describing what happened -- that's the
#     "contract" the rest of the system relies on to know whether something
#     succeeded and what the answer was.
#   - "Deep Research" is Gemini's multi-step research-agent mode (it plans
#     out a research approach, works through it over a few minutes, then
#     writes a report). The official `gemini_webapi` library's built-in
#     support for checking on that in-progress research turned out to be
#     broken against Gemini's current behavior (documented in detail right
#     above `_run_deep_research` below), so this file works around it with
#     its own polling logic.
#   - Nothing about your Google password is ever stored by this file or by
#     Workbrain -- only the temporary session cookies, exactly like staying
#     logged into a website.
# =============================================================================

# 14_Adapters/gemini_bridge/gemini_bridge.py
import sys
sys.dont_write_bytecode = True

import os
import time
import json
import asyncio
import argparse
from pathlib import Path
from typing import List, Optional
from playwright.sync_api import sync_playwright

# gemini_webapi logs via loguru straight to stderr by default. core_router.py appends
# captured stderr after stdout in the response it hands back to the UI, which corrupts
# the single-line JSON payload printed below (extra lines after the closing brace).
# Silence it so stdout/stderr only ever carry our own JSON.
from loguru import logger as _loguru_logger
_loguru_logger.remove()

# Same MOCK_MODE / [MOCK ...] contract as claude_bridge.py, chatgpt_bridge.py, and
# notebooklm_bridge.py -- lets ask_gemini()/generate_image() run without a live
# signed-in Playwright/Edge session. Real (non-mock) behavior is unchanged when off.
MOCK_MODE = os.environ.get("GEMINI_MOCK_MODE", "1") != "0"

# Locate the root workbrain directory, matching copilot_bridge.py's layout
SCRIPT_PATH = Path(__file__).resolve()
ROOT_DIR = SCRIPT_PATH.parents[2]  # gemini_bridge -> 14_Adapters -> project root

# Where the saved Gemini login lives (right next to this file), and the web
# address for Gemini's chat app.
USER_DATA_DIR = SCRIPT_PATH.parent / "gemini_browser_profile"
USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

GEMINI_URL = "https://gemini.google.com/app"


def purge_browser_profile_locks() -> None:
    """Same lock-file hardening as copilot_bridge.py, adapted to this profile dir."""
    # Chromium-based browsers (Edge included) write a small file called
    # "SingletonLock" while running, as a way of saying "I'm already open,
    # don't open me again." If a previous automated run didn't shut down
    # cleanly, that file can be left behind and block every future attempt
    # to reuse this saved login -- even though nothing is actually running
    # anymore. This function detects and clears that stale file before we
    # try to launch anything.
    lock_file = USER_DATA_DIR / "SingletonLock"
    if lock_file.exists():
        try:
            lock_file.unlink()
            print("[CLEANUP] Successfully unlinked stale browser profile SingletonLock handles.")
        except PermissionError:
            # If we can't even delete the lock file, something is still
            # actively using it -- most likely a leftover Edge process from
            # an earlier run that didn't fully close. Try to force-close
            # small/likely-orphaned Edge processes before trying again.
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


def initialize_edge_profile() -> None:
    """
    Launches a visible Edge window against gemini.google.com so the user can complete
    their organization's shared Google/Microsoft SSO login once. The resulting session
    cookies persist on disk in USER_DATA_DIR for every later headless call to reuse --
    no API key involved anywhere in this flow.
    """
    # This is the ONE-TIME SETUP step. It's the only place in this file
    # where a browser window is actually shown on screen -- everything
    # else runs invisibly in the background afterward.
    print("[INIT] Launching Edge headed browser context for authentication...")
    print(f"[PATH] Session profile directory: {USER_DATA_DIR}")

    purge_browser_profile_locks()

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA_DIR),
            channel="msedge",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.new_page()
        page.goto(GEMINI_URL)

        print("\n==================================================")
        print("[ACTION REQUIRED] Sign in to your Google account (routed")
        print("through your organization's shared SSO) in the newly opened")
        print("Edge window now. This session will remain open for 3 minutes.")
        print("Once the Gemini chat UI loads completely, you can close the")
        print("Edge window or wait for the timeout.")
        print("==================================================\n")

        # Keep the window open for up to 3 minutes (180 seconds), checking
        # once a second whether the user has already closed it themselves.
        try:
            for _ in range(180):
                if page.is_closed():
                    break
                time.sleep(1)
        except Exception:
            pass

        context.close()
        print("[SUCCESS] Gemini authentication session profile initialized.")


def _get_session_cookies() -> tuple:
    """
    Launches the persisted profile headlessly just long enough to read back the two
    session cookies gemini-webapi needs (__Secure-1PSID / __Secure-1PSIDTS), then closes
    immediately. All actual Gemini calls happen afterwards over plain HTTP via
    gemini-webapi -- this is the only place Playwright touches the live page.
    """
    # Think of this function as: "open the saved login just long enough to
    # peek at the keycard, then put the browser away." It never actually
    # reads or writes anything on the Gemini chat page itself.
    purge_browser_profile_locks()

    chrome_switches = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--mute-audio",
        "--no-first-run",
        "--disable-extensions",
        "--headless=new",
        "--disable-gpu",
        "--disable-software-rasterizer",
    ]

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA_DIR),
            channel="msedge",
            headless=True,
            args=chrome_switches,
        )
        # Cookies are small pieces of text a website stores in your browser
        # to remember who you are between visits. These two specific ones
        # are what prove to Google's servers that this is a logged-in
        # session.
        cookies = context.cookies("https://gemini.google.com")
        context.close()

    cookie_map = {c["name"]: c["value"] for c in cookies}
    psid = cookie_map.get("__Secure-1PSID")
    psidts = cookie_map.get("__Secure-1PSIDTS", "")

    if not psid:
        # No login cookie found at all means nobody has ever completed the
        # one-time sign-in step (or the saved login has expired/been
        # cleared) -- tell the caller clearly what to do about it rather
        # than failing with a cryptic error further down the line.
        raise RuntimeError(
            "No signed-in Gemini session found in the local browser profile. Run the "
            "'Initialize Session Auth' action first to sign in once via your machine's "
            "existing Google/Microsoft SSO -- no API key is used or required."
        )
    return psid, psidts


async def _run_deep_research(client, prompt: str, poll_interval: float = 15.0, timeout: float = 600.0) -> str:
    """
    gemini_webapi==2.0.0's built-in client.deep_research() waits on plan.research_id,
    but neither the plan-proposal nor the start-confirmation response from Gemini
    currently carries a parseable research_id (confirmed by direct inspection -- both
    come back None, and the confirmation reply itself is an empty-text "immersive chip"
    widget). That makes wait_for_deep_research() always raise immediately.
    Work around it by polling the chat directly via its cid instead of the broken
    research_id/status RPC -- fetch_latest_chat_response is the same documented method
    the library uses internally for fallback recovery.
    """
    # Step 1: ask Gemini to propose a research plan for this topic.
    plan = await client.create_deep_research_plan(prompt)
    # Step 2: tell Gemini to actually start carrying out that plan. This can
    # take several minutes to fully finish in the background.
    await client.start_deep_research(plan)

    if not plan.cid:
        raise RuntimeError("Deep research started but no chat id was returned to poll for the result.")

    # Step 3: since we can't reliably ask "are you done yet?" (see the
    # explanation above), we instead just keep re-checking the
    # conversation every `poll_interval` seconds and watch for a real,
    # substantial report to eventually replace the short "I'm working on
    # it" placeholder message.
    start = time.time()
    while time.time() - start < timeout:
        await asyncio.sleep(poll_interval)
        output = await client.fetch_latest_chat_response(plan.cid)
        # The in-progress acknowledgement ("Great, I'm on it...") comes back as an
        # empty-text widget turn -- keep polling past short/empty responses until the
        # actual report replaces it.
        if output and output.text and len(output.text.strip()) > 200:
            return output.text.strip()

    raise RuntimeError(f"Deep research timed out after {timeout}s without a completed report.")


async def _ask_async(psid: str, psidts: str, prompt: str, deep_research: bool = False, files: Optional[List[str]] = None, gem=None) -> str:
    # Everything in this file that actually talks to Gemini has to go
    # through gemini_webapi's "client" object, which is why this function
    # (and the one below it) both start by creating and initializing one
    # using the login cookies we already fetched.
    from gemini_webapi import GeminiClient

    client = GeminiClient(psid, psidts)
    await client.init(timeout=30, auto_refresh=False)

    if deep_research:
        return await _run_deep_research(client, prompt)

    # Plain, single-turn question-and-answer -- the normal case. `files` (image/
    # document paths) is gemini_webapi's own documented multimodal support --
    # confirmed by inspecting the installed package's generate_content signature.
    # `gem` (a Gem object -- see ask_gemini_gem below) grounds the response in a
    # Gem's custom instructions/dataset, the same documented parameter.
    response = await client.generate_content(prompt, files=files, gem=gem)
    return (response.text or "").strip()


async def _fetch_gems_async(psid: str, psidts: str):
    """Returns gemini_webapi's GemJar (dict of id -> Gem) of every Gem available
    to the signed-in account -- predefined and custom, each with its own
    instructions/dataset loaded via the Gem interface."""
    from gemini_webapi import GeminiClient

    client = GeminiClient(psid, psidts)
    await client.init(timeout=30, auto_refresh=False)
    return await client.fetch_gems()


async def _generate_image_async(psid: str, psidts: str, prompt: str, output_dir: str) -> str:
    from gemini_webapi import GeminiClient

    client = GeminiClient(psid, psidts)
    await client.init(timeout=30, auto_refresh=False)

    response = await client.generate_content(prompt)
    if not response.images:
        raise RuntimeError("Gemini returned no images (the prompt may have been blocked, or Gemini replied with text only).")

    # Save the first generated image to disk under a name that includes
    # the current time, so repeated calls never overwrite each other.
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"gemini_image_{int(time.time())}.png"
    await response.images[0].save(path=str(out_dir), filename=filename, verbose=False)
    return str(out_dir / filename)


def ask_gemini(prompt: str, use_search: bool = False, files: Optional[List[str]] = None) -> str:
    """Text generation, optionally with attached image/document files (multimodal --
    OCR, image description, form extraction, etc.). use_search=True runs it as a full
    Deep Research pass instead; combining that with files isn't supported (Deep
    Research is a multi-step research pass over a topic, not a single-turn multimodal
    question -- a deliberate Cortex-side restriction, not a gemini_webapi limitation)."""
    if use_search and files:
        raise ValueError("ask_gemini: use_search (Deep Research) and files can't be combined.")
    if MOCK_MODE:
        mode = "search-grounded " if use_search else ""
        file_note = f" [with {len(files)} attached file(s)]" if files else ""
        return f"[MOCK {mode}Gemini response{file_note}] {prompt[:300]}"
    # Public entry point used by main() below. Handles the "get the login
    # cookies, then run the actual async Gemini call" sequence in one step.
    psid, psidts = _get_session_cookies()
    return asyncio.run(_ask_async(psid, psidts, prompt, deep_research=use_search, files=files))


def list_gems() -> list:
    """Returns every Gem available to the signed-in account: [{"id", "name",
    "description"}] -- Gemini's equivalent of M365 Copilot Agents (see
    copilot_bridge.list_agents), a reusable persona with its own custom
    instructions and dataset loaded via the Gem interface."""
    if MOCK_MODE:
        return [
            {"id": "mock-gem-1", "name": "Career Coach", "description": "[MOCK] Predefined Gemini Gem."},
            {"id": "mock-gem-2", "name": "Curriculum Reviewer", "description": "[MOCK] Custom Gem with a loaded dataset."},
        ]
    psid, psidts = _get_session_cookies()
    gems = asyncio.run(_fetch_gems_async(psid, psidts))
    return [{"id": g.id, "name": g.name, "description": g.description or ""} for g in gems]


def ask_gemini_gem(gem_name: str, prompt: str) -> str:
    """Grounds a message to a specific Gem by name (see list_gems()) and returns its
    response -- the Gem's own custom instructions/dataset shape the answer, same as
    ask_agent() grounds a message to a specific M365 Copilot agent."""
    if not gem_name:
        raise ValueError("ask_gemini_gem requires a gem_name.")
    if not prompt:
        raise ValueError("ask_gemini_gem requires a prompt.")
    if MOCK_MODE:
        return f"[MOCK Gemini Gem '{gem_name}' response] {prompt[:300]}"
    psid, psidts = _get_session_cookies()
    gems = asyncio.run(_fetch_gems_async(psid, psidts))
    gem = gems.get(name=gem_name)
    if gem is None:
        raise RuntimeError(f"No Gem named '{gem_name}' found. Run list_gems() to see available Gems.")
    return asyncio.run(_ask_async(psid, psidts, prompt, gem=gem))


def generate_image(prompt: str, output_dir: str) -> str:
    """Generates one image via Gemini's built-in image generation, saved to output_dir."""
    if MOCK_MODE:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = f"gemini_image_mock_{int(time.time())}.png"
        (out_dir / filename).write_bytes(b"\x89PNG\r\n\x1a\n")
        return str(out_dir / filename)
    psid, psidts = _get_session_cookies()
    return asyncio.run(_generate_image_async(psid, psidts, prompt, output_dir))


def main():
    # This is what actually runs when core_router.py (or you, from a
    # terminal) executes this file. It expects one command-line argument:
    # a small JSON instruction describing what to do, for example:
    #   {"action": "ask", "prompt": "What's the capital of France?"}
    # It always prints back exactly one line of JSON describing the
    # result -- either {"success": true, "response"/"file_path": ...} or
    # {"success": false, "response": "<error message>"}. This is the
    # "contract" every caller of this script relies on.
    parser = argparse.ArgumentParser(description="Workbrain Gemini Integration Bridge (browser-session based, no API key)")
    parser.add_argument("payload", nargs="?", default="", help="Inline JSON parameter from router")
    args = parser.parse_args()

    if not args.payload:
        print(json.dumps({
            "success": False,
            "response": 'No JSON payload provided. Expected: {"action": "init|ask|search|generate_image|list_gems|ask_gem", "prompt": "..."}',
        }))
        sys.exit(1)

    try:
        params = json.loads(args.payload)
    except json.JSONDecodeError as e:
        print(json.dumps({"success": False, "response": f"Malformed JSON payload: {e}"}))
        sys.exit(1)

    action = params.get("action", "ask")

    # "init" is the one-time interactive sign-in flow -- see
    # initialize_edge_profile() above. Every other action assumes that has
    # already been done at least once.
    if action == "init":
        initialize_edge_profile()
        print(json.dumps({"success": True, "response": "Gemini authentication session profile initialized."}))
        return

    prompt = params.get("prompt", "")

    try:
        if action == "ask":
            result = {"success": True, "response": ask_gemini(prompt, use_search=False)}
        elif action == "search":
            # "search" runs the prompt through Gemini's Deep Research mode
            # instead of a normal single-turn answer.
            result = {"success": True, "response": ask_gemini(prompt, use_search=True)}
        elif action == "generate_image":
            output_dir = params.get("output_dir") or str(ROOT_DIR / "02_vault" / "generated_images")
            result = {"success": True, "file_path": generate_image(prompt, output_dir)}
        elif action == "list_gems":
            result = {"success": True, "gems": list_gems()}
        elif action == "ask_gem":
            result = {"success": True, "response": ask_gemini_gem(params.get("gem_name", ""), prompt)}
        else:
            result = {"success": False, "response": f"Unknown action: {action}"}
    except Exception as e:
        # Catch absolutely everything here rather than letting the script
        # crash with a raw Python error -- the caller (core_router.py, the
        # Cortex web app) expects a clean JSON line back no matter what
        # went wrong.
        result = {"success": False, "response": f"Gemini bridge error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)


if __name__ == "__main__":
    main()
