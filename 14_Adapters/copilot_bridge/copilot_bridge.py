# =============================================================================
# copilot_bridge.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   This is the main, production adapter that lets the rest of Workbrain
#   (the Cortex web app, the Workflow Builder, and anything scripted) talk
#   to Microsoft 365 Copilot -- asking it questions, generating images with
#   its built-in Designer feature, and chatting with specific named "agents"
#   (custom Copilot personas your organization has set up, like a
#   "Hal-9000" or "Researcher" agent) by @-mentioning them the same way you
#   would in the actual Copilot chat website.
#
#   It works by remote-controlling a real, invisible copy of Microsoft Edge:
#   opening the Copilot chat page, typing your question into the chat box
#   exactly like a person would, waiting for the answer to finish appearing
#   on screen, and then reading that text back out of the page. There is no
#   Copilot API key involved anywhere -- it rides entirely on your own
#   signed-in Microsoft 365 login.
#
# WHAT IT INTERACTS WITH
#   - Microsoft Edge, automated via the "Playwright" library (this is what
#     actually opens the browser, clicks, types, and reads the page).
#   - Your saved Microsoft 365 login, stored in a folder called
#     "copilot_browser_profile" right next to this file. That folder full
#     of files IS your saved login -- deleting it, or a stale leftover
#     browser process holding it locked, are the two most common causes of
#     this adapter suddenly failing.
#   - m365.cloud.microsoft (Microsoft's Copilot chat website).
#   - `core_router.py`, which is what actually runs this file when the
#     Cortex web app or Workflow Builder asks for a Copilot action -- you
#     don't normally run this file directly yourself, though you can for
#     manual testing (see `main()` near the bottom for the command format).
#   - `00_System/brain_state.db`, Workbrain's local database, used only
#     as an emergency fallback (see `synthesize_db_fallback_context()`) when
#     a script asks this adapter to read a text file that doesn't exist.
#   - `02_vault/generated_images/`, where AI-generated images get saved by
#     default.
#
# KEY FUNCTIONALITY NOTES
#   - Every action this file can perform is triggered by a small JSON
#     instruction, e.g. {"action": "ask", "prompt": "..."}. This file always
#     prints back exactly one line of JSON describing what happened --
#     that's the "contract" the rest of the system relies on to know
#     whether something succeeded and what the answer was. The supported
#     actions are: init (one-time sign-in), ask (plain question), generate_image
#     (Designer image generation), list_agents (see which agents you can
#     @-mention), and ask_agent (ground a question to one specific agent).
#   - "Reading the answer off the page" is trickier than it sounds, because
#     Copilot's answer appears gradually (like watching someone type live),
#     and sometimes shows temporary "searching your files..." style messages
#     before the real answer. Most of the logic in this file
#     (`is_preliminary_response`, `_await_response`) exists specifically to
#     wait out those interruptions and know when the real, final answer has
#     actually finished appearing.
#   - The "@" agent-mention feature works by typing "@" plus the agent's
#     name into the chat box, which opens a small pop-up list of matching
#     agents (the exact same list you'd see doing this by hand on the
#     Copilot website); clicking the right entry attaches a small visual
#     "chip" to the message saying which agent it's directed at, and then
#     the rest of the flow (type the real question, submit, wait for an
#     answer) is identical to a normal question.
#   - Nothing about your Microsoft password is ever stored by this file or
#     by Workbrain -- only the browser's own saved login session, exactly
#     like staying logged into a website in your normal browser.
# =============================================================================

# 14_Adapters/copilot_bridge/copilot_bridge.py
import sys
# Globally suppress compiled bytecode (.pyc) disk writes inside our tracking context
sys.dont_write_bytecode = True

import os
import time
import json
import base64
import argparse
import urllib.parse
import sqlite3
from pathlib import Path
from playwright.sync_api import sync_playwright

# The one web address every action in this file eventually navigates to:
# Microsoft's Copilot chat page.
NAV_URL = "https://m365.cloud.microsoft/chat/"

# Agent-picker pseudo-entries that appear in the "@" mention menu but aren't real
# agents (e.g. a "Get agents" link to the store) -- never treat these as matches.
NON_AGENT_MENTION_LABELS = {"get agents"}

# Locate the root workbrain directory (for DB_PATH only -- USER_DATA_DIR lives right
# next to this file, so it doesn't need to climb anywhere).
SCRIPT_PATH = Path(__file__).resolve()
ROOT_DIR = SCRIPT_PATH.parents[2]  # copilot_bridge -> 14_Adapters -> project root
USER_DATA_DIR = SCRIPT_PATH.parent / "copilot_browser_profile"
DB_PATH = ROOT_DIR / "00_System" / "brain_state.db"

# Guarantee target directory locus existence
USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

def clean_copilot_response(raw_text: str) -> str:
    """
    Cleans raw scrapings of the M365 Copilot response container.
    Removes common Microsoft UI elements, buttons, and feedback footers.
    """
    # When we read the answer text directly off the web page, it comes
    # bundled together with button labels that sit right next to it on
    # screen ("Copy", "Share", "Thumbs up", etc.) even though they aren't
    # actually part of what Copilot wrote. This function strips that
    # leftover UI clutter out so only the real written answer remains.
    if not raw_text:
        return ""

    clean_response = raw_text.strip()
    ui_footers = [
        "Provide your feedback on BizChat",
        "Provide your feedback",
        "Feedback",
        "Copy response",
        "Share response",
        "Copy",
        "Share",
        "Thumbs up",
        "Thumbs down",
        "Stop responding",
        "New topic"
    ]
    for footer in ui_footers:
        clean_response = clean_response.replace(footer, "")

    return clean_response.strip()

def is_preliminary_response(text: str) -> bool:
    """
    Evaluates whether the scraped content text is an intermediate status placeholder
    emitted by M365 Copilot while querying SharePoint or OneDrive data.
    """
    # Copilot often shows short "status" messages while it works (e.g.
    # "Searching your organization...") before replacing them with the real
    # answer. If we mistook one of these for the finished answer, we'd
    # return useless placeholder text instead of waiting for the real
    # response. This function is the detector that says "no, that's just a
    # status message, keep waiting."
    if not text:
        return True

    lower_text = text.lower().strip()

    # Comprehensive evaluation block for Microsoft BizChat / M365 Copilot intermediate states
    preliminary_phrases = [
        "looking into it",
        "working on it",
        "searching for",
        "searching across multiple domains",
        "searching your organization",
        "analyzing your files",
        "finding relevant documents",
        "gathering information",
        "gathering details",
        "thinking",
        "just a moment",
        "one moment"
    ]

    for phrase in preliminary_phrases:
        if phrase in lower_text:
            return True

    # Heuristic Shield: If response is short and ends with trailing periods or ellipsis,
    # it is a streaming search/placeholder phase. Do not terminate.
    if len(lower_text) < 350 and (lower_text.endswith("...") or lower_text.endswith("…")):
        return True

    return False

def synthesize_db_fallback_context() -> str:
    """
    Programmatic Resiliency Hook: Queries active SQLite state schemas to assemble
    a high-fidelity live system dataset slice when targeted inbox text files are missing.
    """
    # This is a safety net used only by the older --input file-path command-line
    # option (see main() below): if a script asks this adapter to read a text
    # file for context and that file turns out not to exist, rather than just
    # failing outright, this function builds a small useful summary straight
    # out of Workbrain's own database instead (recent contacts, transcripts,
    # and class counts) so the request can still proceed with *something*
    # meaningful to work with.
    print("[FALLBACK] Synthesizing system data context from core SQLite database engine...")
    if not DB_PATH.exists():
        return "Workbrain Automated State Context: Core database tracking engine file is currently unreachable."

    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 1. Harvest top active contact portfolio matrices
        cursor.execute("SELECT name, email, trade, total_engagements, company FROM contacts ORDER BY total_engagements DESC LIMIT 5;")
        contacts = cursor.fetchall()

        # 2. Harvest recent indexed transcript file maps
        cursor.execute("SELECT title, trade, source_type FROM transcripts_metadata ORDER BY id DESC LIMIT 4;")
        transcripts = cursor.fetchall()

        # 3. Compile summary statistics metrics across active trades
        cursor.execute("SELECT trade, COUNT(*) as class_count FROM training_classes GROUP BY trade;")
        trade_summary = cursor.fetchall()

        conn.close()

        context_str = "WORKBRAIN CORE ENGINE INTERCEPT: Missing File Context Substituting With Live Relational Database State.\n\n"
        context_str += "=== CRITICAL ACTIVE SUBJECT MATTER EXPERTS ===\n"
        for c in contacts:
            context_str += f"- Expert Name: {c['name']} | Channel: {c['email']} | Field Focus: {c['trade']} | Total Meetings Attended: {c['total_engagements']} | Regional Zone: {c['company']}\n"

        context_str += "\n=== RECENT LONG-TERM TRANSCRIBED MEETING META ===\n"
        for t in transcripts:
            context_str += f"- Resource Scope: [{t['source_type']}] {t['title']} | Grounding Field Mapping: {t['trade']}\n"

        context_str += "\n=== SYSTEM ENROLLMENT DISTRIBUTION SUMMARIES ===\n"
        for ts in trade_summary:
            context_str += f"- Trade Framework Area: {ts['trade']} -> Active Monitored Class Pipelines: {ts['class_count']}\n"

        return context_str

    except Exception as err:
        return f"Workbrain Automated State Context: Query synthesis trace error exception thrown: {str(err)}"

def purge_browser_profile_locks() -> None:
    """
    Harden Windows Profile Safety: Forcefully clears lock parameters and unlinks
    dangling file state handles to prevent Playwright from bypassing the headless argument.
    """
    # Chromium-based browsers (Edge included) write a small file called
    # "SingletonLock" while running, as a way of saying "I'm already open,
    # don't open me again." If a previous automated run didn't shut down
    # cleanly, that file (or an actual leftover Edge process) can be left
    # behind and block every future attempt to reuse this saved login, even
    # though nothing useful is still running. This function detects and
    # clears that stale state before we try to launch anything.
    lock_file = USER_DATA_DIR / "SingletonLock"
    if lock_file.exists():
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

def initialize_edge_profile() -> None:
    """
    Launches a visible Edge window to prompt user sign-in to M365.
    Saves authentication profile tokens inside the local directory.
    """
    # This is the ONE-TIME SETUP step (triggered by the Cortex web app's
    # "Initialize Session Auth" button, or the {"action": "init"} JSON
    # instruction). It's the only place in this file where a browser
    # window is actually shown on screen -- every other action runs
    # invisibly in the background afterward, reusing the login saved here.
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
        page.goto("https://m365.cloud.microsoft/chat/")

        print("\n==================================================")
        print("[ACTION REQUIRED] Log in to your enterprise M365")
        print("account in the newly opened Edge window now.")
        print("This browser session will remain open for 3 minutes.")
        print("Once your work chat layout loads completely, you can")
        print("close the Edge window or wait for the timeout.")
        print("==================================================\n")

        # Keep the window open for up to 3 minutes (180 seconds), checking
        # once a second whether the user has already closed it themselves.
        try:
            for s in range(180):
                if page.is_closed():
                    break
                time.sleep(1)
        except Exception:
            pass

        context.close()
        print("[SUCCESS] Microsoft Edge authentication session profile initialized.")

def _chrome_switches(headless: bool) -> list:
    """Builds the list of low-level Edge/Chromium startup flags used for every
    automated launch. These tune the browser for unattended, invisible operation
    (disable auto-update prompts, avoid using the real desktop's audio/graphics,
    etc.) rather than a normal interactive browsing session."""
    switches = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--mute-audio",
        "--no-first-run",
        "--disable-extensions"
    ]
    if headless:
        # Inject modern windowless switches to disconnect browser runtime from the active desktop handle
        switches.extend(["--headless=new", "--disable-gpu", "--disable-software-rasterizer"])
    return switches


def _launch_context(p, headless: bool):
    """Shared launch helper used by every action below (ask, generate_image,
    list_agents, ask_agent): clears any stale lock first, then opens Edge
    using the saved login profile. `headless=True` (the default for all
    automated/production calls) means the browser window is invisible;
    `headless=False` is only used for the one-time interactive sign-in."""
    purge_browser_profile_locks()
    return p.chromium.launch_persistent_context(
        user_data_dir=str(USER_DATA_DIR),
        channel="msedge",
        headless=headless,
        args=_chrome_switches(headless)
    )


def _submit_prompt(page, prompt_text: str) -> None:
    """Types prompt_text into the chat compose box and submits it. Assumes the box
    may already contain a grounding chip (from _select_agent_mention) -- fill() is
    avoided in favor of type() so an existing chip isn't clobbered."""
    chat_box = page.locator("textarea, [role='textbox'], #aria-web-chat-input-textarea").first
    chat_box.wait_for(state="visible", timeout=10000)
    # The compose box renders before the chat app is fully interactive -- typing
    # immediately can get silently dropped. Give it a moment (harmless no-op if a
    # grounding chip flow already settled the page).
    page.wait_for_timeout(2500)
    chat_box.click()
    chat_box.type(prompt_text, delay=5)
    page.wait_for_timeout(1000)

    print("[PLAYWRIGHT] Submitting prompt sequence...")
    # Prefer clicking the visible "Send" button if there is one; if the page
    # doesn't show one (or it's hidden), fall back to just pressing Enter,
    # which normal chat websites also treat as "send this message."
    send_btn = page.locator(
        "button[aria-label*='Send'], button[aria-label*='Submit'], button:has-text('Send'), [data-testid='send-button']"
    ).first
    if send_btn.is_visible():
        send_btn.click()
    else:
        chat_box.press("Enter")
    page.wait_for_timeout(2000)


def _await_response(page, prompt_text: str, timeout: int = 75) -> str:
    """Polls the chat pane for a settled, non-preliminary response and returns cleaned text."""
    # Copilot's answer streams in gradually rather than appearing all at
    # once, so we can't just read the page one time. Instead this loop
    # re-checks the visible text roughly once a second and considers the
    # answer "finished" once its length has stopped growing for 4 checks
    # in a row (see the stable_count logic below) AND it isn't one of the
    # temporary "searching..." style placeholder messages.
    print("[PLAYWRIGHT] Waiting for Copilot grounding and generation...")
    start_time = time.time()
    last_length = 0
    stable_count = 0
    final_response = ""

    # Copilot's web page can render its answer inside different container
    # types depending on the kind of response (plain text, a card, etc.),
    # so all of these are checked and whichever currently holds real
    # content is used.
    selectors = [
        "[data-content='ai-message']",
        ".ac-container",
        "[role='presentation']",
        "[role='article']",
        ".message-content",
        "div.chat-message-content"
    ]

    while time.time() - start_time < timeout:
        current_text = ""
        for selector in selectors:
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

        is_prelim = is_preliminary_response(current_text_clean)

        if is_prelim:
            if current_length != last_length:
                print(f" -> [COPILOT STATUS] Background task in progress: '{current_text_clean[:60]}...'")
            stable_count = 0
            last_length = current_length
        elif current_length > 0 and current_length == last_length:
            stable_count += 1
            # Require 4 consecutive seconds of zero-growth stability on real content before ending block
            if stable_count >= 4:
                final_response = current_text_clean
                break
        else:
            stable_count = 0
            last_length = current_length

        time.sleep(1)

    # If nothing above ever produced a confident final answer within the
    # timeout, fall back to grabbing the entire visible page text and
    # trying to salvage an answer out of whatever comes after the question
    # we asked -- a last resort, but better than returning nothing.
    if not final_response:
        print("[WARNING] Primary response selectors timed out. Engaging fallback...")
        try:
            page_text = page.locator("body").text_content()
            if prompt_text in page_text:
                parts = page_text.split(prompt_text)
                final_response = parts[-1].strip()
            else:
                final_response = page_text[-1500:].strip()
        except Exception as e:
            final_response = f"Failed fallback scrape: {str(e)}"

    return clean_copilot_response(final_response)


def _iter_mention_agents(page):
    """Yields (menuitem_locator, name, description) for every real agent currently
    shown in the "@" mention popup, skipping non-agent pseudo-entries like "Get agents"."""
    # When you type "@" into Copilot's chat box, a small pop-up list of
    # agents appears -- the exact same list you'd see doing this by hand.
    # This function reads that pop-up and hands back each agent's name and
    # short description, one at a time, so both list_agents() and
    # _select_agent_mention() below can reuse the same reading logic.
    for item in page.locator("[role='menuitem']").all():
        try:
            avatar = item.locator("[role='img']").first
            name = (avatar.get_attribute("aria-label") or "").strip()
            if not name or name.lower() in NON_AGENT_MENTION_LABELS:
                continue
            description = ""
            try:
                desc_el = item.locator("span.fai-BebopGroundingMenuItem__secondaryText").first
                description = (desc_el.text_content() or "").strip()
            except Exception:
                pass
            yield item, name, description
        except Exception:
            continue


def _select_agent_mention(page, agent_name: str) -> str:
    """Opens the '@' mention picker, selects the agent matching agent_name (exact match
    preferred, falls back to substring), and leaves a grounding chip in the compose box.
    Returns the resolved agent display name. Raises RuntimeError if no match is found."""
    chat_box = page.locator("textarea, [role='textbox'], #aria-web-chat-input-textarea").first
    chat_box.wait_for(state="visible", timeout=10000)
    # The textbox renders before the mention picker's agent-provider data has loaded --
    # typing "@" too early yields an empty/stale popup even though the box is visible.
    page.wait_for_timeout(2500)
    chat_box.click()
    chat_box.type("@" + agent_name, delay=40)
    page.wait_for_timeout(1500)

    # Prefer an exact name match ("Hal-9000" == "Hal-9000"); if none is
    # found, fall back to the first agent whose name merely contains what
    # was typed, so a caller can get away with typing a shorter/partial name.
    exact_match = None
    partial_match = None
    for item, name, _desc in _iter_mention_agents(page):
        if name.lower() == agent_name.strip().lower():
            exact_match = (item, name)
            break
        if partial_match is None and agent_name.strip().lower() in name.lower():
            partial_match = (item, name)

    match = exact_match or partial_match
    if not match:
        raise RuntimeError(f"No agent matching '{agent_name}' found in the @ mention list.")

    # Clicking the matched entry inserts a small visual "chip" naming the
    # agent into the compose box -- it does NOT navigate to a different
    # page or open a separate conversation. Everything typed afterward in
    # the same box is understood as being directed at that agent.
    item, resolved_name = match
    item.click()
    page.wait_for_timeout(500)
    return resolved_name


def list_agents(headless: bool = True) -> list:
    """Returns the agents available to @-mention in chat: [{"name": ..., "description": ...}]."""
    # This opens a fresh browser session purely to peek at the "@" mention
    # pop-up list and read out every agent's name/description -- it doesn't
    # send any actual message. Useful for a caller (e.g. the Cortex web
    # app's agent dropdown) that wants to show you the full list of agents
    # before you pick which one to talk to.
    with sync_playwright() as p:
        context = _launch_context(p, headless)
        try:
            page = context.new_page()
            page.goto(NAV_URL)
            chat_box = page.locator("textarea, [role='textbox'], #aria-web-chat-input-textarea").first
            chat_box.wait_for(state="visible", timeout=15000)
            page.wait_for_timeout(2500)
            chat_box.click()
            chat_box.type("@", delay=40)
            page.wait_for_timeout(1500)

            agents = []
            seen = set()
            for _item, name, description in _iter_mention_agents(page):
                if name in seen:
                    continue
                seen.add(name)
                agents.append({"name": name, "description": description})
            return agents
        finally:
            # Always close the browser context, even if something above
            # raised an error -- otherwise we'd leak an invisible Edge
            # process that could later block/lock this same profile.
            context.close()


def ask_agent(agent_name: str, prompt_text: str, headless: bool = True) -> str:
    """Grounds a message to a specific agent via '@agent_name' and returns its response."""
    if not agent_name:
        raise ValueError("No agent name provided.")
    if not prompt_text:
        raise ValueError("No prompt context provided.")

    with sync_playwright() as p:
        context = _launch_context(p, headless)
        try:
            page = context.new_page()
            page.goto(NAV_URL)
            # Step 1: attach the "@AgentName" chip to the compose box.
            resolved_name = _select_agent_mention(page, agent_name)
            print(f"[PLAYWRIGHT] Grounded to agent: {resolved_name}")
            # Step 2: type the actual question after the chip and submit it.
            _submit_prompt(page, prompt_text)
            # Step 3: wait for and read back that specific agent's answer.
            return _await_response(page, prompt_text)
        finally:
            context.close()


def generate_image(prompt_text: str, output_dir: str, headless: bool = True) -> str:
    """Asks Copilot's built-in Designer plugin to generate an image, saved to output_dir.
    Copilot renders the result inline as a base64 data URI image (alt text ending in
    " Image"), so no download step is needed -- just decode and write it."""
    # "base64" is a way of representing an image's raw bytes as plain text,
    # so it can be embedded directly inside a web page instead of being a
    # separate file to download. Copilot's Designer feature returns
    # generated images this way, which is actually convenient for us: we
    # can just decode that text back into real image bytes and save it,
    # with no separate "click download" step needed.
    if not prompt_text:
        raise ValueError("No prompt context provided.")

    with sync_playwright() as p:
        context = _launch_context(p, headless)
        try:
            page = context.new_page()
            page.goto(NAV_URL)
            _submit_prompt(page, prompt_text)

            print("[PLAYWRIGHT] Waiting for Copilot Designer image generation...")
            # Every image Copilot generates gets an "alt text" (an
            # accessibility description) that ends in the word " Image" --
            # that's a reliable, prompt-independent way to spot the
            # generated picture among all the other small icons/avatars
            # also present on the page.
            img_locator = page.locator("img[alt$=' Image']")
            try:
                img_locator.first.wait_for(state="visible", timeout=90000)
            except Exception:
                # No image ever appeared. Grab whatever text Copilot did settle on so the
                # caller sees *why* (most commonly Designer's own rate limit -- M365 Copilot
                # caps image generations per day/session and then answers with empty/plain
                # text instead of an explicit error) instead of a bare Playwright timeout.
                fallback_text = _await_response(page, prompt_text, timeout=5)
                raise RuntimeError(
                    "Copilot did not return a generated image in time -- it may have hit its "
                    "own image-generation rate limit, or answered with text instead of invoking "
                    f"Designer. Copilot's response was: {fallback_text[:300]!r}"
                )
            src = img_locator.last.get_attribute("src") or ""

            if not src.startswith("data:image"):
                raise RuntimeError("Copilot did not return an inline generated image (the prompt may have been blocked).")

            # The embedded image data looks like "data:image/png;base64,<lots of characters>" --
            # split off the "data:image/png;base64," header so only the actual encoded
            # picture data is left, then decode that back into real image bytes.
            header, b64data = src.split(",", 1)
            ext = "png" if "png" in header else "jpg"
            out_dir = Path(output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            filename = f"copilot_image_{int(time.time())}.{ext}"
            file_path = out_dir / filename
            file_path.write_bytes(base64.b64decode(b64data))
            return str(file_path)
        finally:
            context.close()


def ask_copilot(prompt_text: str, headless: bool = True) -> str:
    """
    Launches Microsoft Edge, automates prompt injection, and extracts response content.
    Enforces strict underlying Chromium flags to guarantee absolute windowless execution.
    """
    # The plain, simplest case: ask one question, get one answer back, no
    # file attachments, no specific agent. This is what the Cortex web
    # app's basic "Ask Copilot" mode uses.
    if not prompt_text:
        return "Error: No prompt context provided."

    print(f"[PLAYWRIGHT] Executing Copilot workflow (Enforced Headless={headless})...")
    print(f"[PLAYWRIGHT] Target profile directory: {USER_DATA_DIR}")

    with sync_playwright() as p:
        try:
            context = _launch_context(p, headless)
            page = context.new_page()
            page.goto(NAV_URL)

            print("[PLAYWRIGHT] Locating chat input area...")
            _submit_prompt(page, prompt_text)
            response = _await_response(page, prompt_text)
            context.close()
            return response

        except Exception as err:
            # Unlike the newer generate_image/list_agents/ask_agent functions
            # (which raise real errors for the caller to catch), this older
            # function instead returns the error as if it were the answer
            # text, prefixed so callers can still recognize it as a failure
            # -- see `succeeded = not response.startswith(...)` in main() below.
            try:
                context.close()
            except Exception:
                pass
            return f"Automation Interface Exception: {str(err)}"

def main():
    # This is what actually runs when core_router.py (or you, from a
    # terminal) executes this file. It supports two different calling
    # styles at once, for backward compatibility:
    #   1. The modern one: a single JSON instruction, e.g.
    #      python copilot_bridge.py "{\"action\": \"ask\", \"prompt\": \"...\"}"
    #      This is how the Cortex web app and Workflow Builder always call it.
    #   2. The older, more manual command-line-flag style (--prompt,
    #      --input, --output, --template, etc.), kept working for any
    #      existing scripts/examples that still use it directly.
    # Either way, when driven by a JSON instruction, this always prints back
    # exactly one line of JSON describing the result -- that's the
    # "contract" every caller of this script relies on.
    parser = argparse.ArgumentParser(description="Workbrain M365 Copilot Integration Bridge")
    parser.add_argument("--init-profile", action="store_true", help="Launch interactive Edge browser for setup")
    parser.add_argument("--prompt", type=str, help="Plaintext prompt query to submit directly")
    parser.add_argument("--input", type=str, help="Filepath containing text input to be analyzed")
    parser.add_argument("--output", type=str, help="Filepath to write the finalized clean Copilot response text")
    parser.add_argument("--template", type=str, help="Custom prompt envelope context.")
    parser.add_argument("--headed", action="store_true", help="Force Edge to execute in a visible headed UI window")
    parser.add_argument("payload", nargs="?", default="", help="Inline JSON parameter from router")

    args = parser.parse_args()
    prompt_to_run = ""

    # Enforce headless execution by default for all automation flows
    execution_headless = True
    if args.headed:
        execution_headless = False

    if not sys.stdin.isatty():
        prompt_to_run = sys.stdin.read().strip()

    if args.payload and not prompt_to_run:
        try:
            params = json.loads(args.payload)
            action = params.get("action", "")
            if "headless" in params:
                execution_headless = params.get("headless")

            # "init" is the one-time interactive sign-in flow -- see
            # initialize_edge_profile() above.
            if action == "init":
                initialize_edge_profile()
                print(json.dumps({"success": True, "response": "Copilot authentication session profile initialized."}))
                return
            elif action == "ask":
                prompt_to_run = params.get("prompt", "")
            elif action == "generate_image":
                prompt = params.get("prompt", "")
                output_dir = params.get("output_dir") or str(ROOT_DIR / "02_vault" / "generated_images")
                try:
                    file_path = generate_image(prompt, output_dir, headless=execution_headless)
                    print(json.dumps({"success": True, "file_path": file_path}))
                except Exception as e:
                    print(json.dumps({"success": False, "response": f"Copilot bridge error: {e}"}))
                    sys.exit(1)
                return
            elif action == "list_agents":
                try:
                    agents = list_agents(headless=execution_headless)
                    print(json.dumps({"success": True, "agents": agents}))
                except Exception as e:
                    print(json.dumps({"success": False, "response": f"Copilot bridge error: {e}"}))
                    sys.exit(1)
                return
            elif action == "ask_agent":
                agent_name = params.get("agent", "")
                prompt = params.get("prompt", "")
                try:
                    response = ask_agent(agent_name, prompt, headless=execution_headless)
                    print(json.dumps({"success": True, "response": response}))
                except Exception as e:
                    print(json.dumps({"success": False, "response": f"Copilot bridge error: {e}"}))
                    sys.exit(1)
                return
        except Exception:
            # If the payload wasn't valid JSON at all, fall through and treat
            # it as if it were just a plain-text prompt typed in directly.
            prompt_to_run = args.payload

    # --- Legacy command-line-flag path (not used by the Cortex web app,
    # kept for manual/scripted use) ---
    if not prompt_to_run:
        if args.init_profile:
            initialize_edge_profile()
            return
        elif args.prompt:
            prompt_to_run = args.prompt
        elif args.input:
            input_path = Path(args.input)
            if not input_path.exists():
                print(f"[WARNING] Specified input file context missing at: {input_path}")
                input_text = synthesize_db_fallback_context()
            else:
                with open(input_path, "r", encoding="utf-8", errors="ignore") as f:
                    input_text = f.read()

            if args.template:
                prompt_to_run = args.template.replace("{input}", input_text)
            else:
                prompt_to_run = input_text

    # If none of the above supplied a question, fall back to asking
    # interactively right in the terminal.
    if not prompt_to_run:
        print("==================================================")
        print("   M365 COPILOT INTERACTIVE CONSOLE INTEGRATION  ")
        print("==================================================\n")
        try:
            prompt_to_run = input("Enter your M365 Copilot prompt: ").strip()
            execution_headless = False
        except (KeyboardInterrupt, EOFError):
            print("\n[ABORT] Bypassed.")
            sys.exit(1)

    if not prompt_to_run:
        print("[ABORT] Empty prompt sequence detected.")
        sys.exit(1)

    response = ask_copilot(prompt_to_run, headless=execution_headless)
    # ask_copilot() (unlike the newer action handlers above) reports failure
    # by returning a specially-prefixed error string rather than raising --
    # this line is how we translate that back into an honest success/fail flag.
    succeeded = not response.startswith("Automation Interface Exception:")

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(response)
        print(f"[SUCCESS] Copilot response safely recorded to: {output_path}")
    else:
        if args.payload:
            print(json.dumps({"success": succeeded, "response": response}))
            if not succeeded:
                sys.exit(1)
        else:
            print("\n=== COPILOT RESPONSE ===")
            print(response)

if __name__ == "__main__":
    main()
