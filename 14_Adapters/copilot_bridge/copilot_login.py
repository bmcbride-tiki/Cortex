# =============================================================================
# copilot_login.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   A small, standalone, one-time setup script. Running it opens a real,
#   visible Microsoft Edge window pointed at the M365 Copilot chat website
#   so a human can log in by hand. Once you log in, Edge saves your session
#   (cookies, login tokens, etc.) to a folder on disk called a "browser
#   profile." Every other script in this adapters/copilot-bridge folder
#   reuses that saved profile to open Copilot chat *without* asking you to
#   log in again -- that's the entire point of this file.
#
# WHAT IT INTERACTS WITH
#   - Microsoft Edge itself (must be installed on this machine).
#   - The "Playwright" library, which is browser-automation software: it can
#     open, click, type into, and read real browser windows under program
#     control, the same way a human would use a mouse and keyboard.
#   - A folder named "copilot_browser_profile" created next to wherever you
#     run this script from. That folder IS the saved login. Deleting it
#     forces you to log in again next time.
#   - m365.cloud.microsoft (Microsoft's live Copilot chat website).
#
# KEY FUNCTIONALITY NOTES
#   - This is superseded by `copilot_bridge.py`'s `initialize_edge_profile()`
#     function, which does the same job but is wired into the rest of the
#     system (the router, the Cortex web UI's "Initialize Session Auth"
#     button). This standalone file is kept around as a quick manual
#     fallback you can run directly from a terminal if that button ever
#     stops working.
#   - The browser window stays open for 5 minutes (300,000 milliseconds) so
#     you have time to complete your organization's login steps (password,
#     multi-factor approval, etc.). You can also just close the window
#     yourself as soon as you're logged in -- you don't have to wait out
#     the full 5 minutes.
#   - No password or account details are stored by this script or by
#     Workbrain. The only thing saved is the browser's own login session,
#     exactly like staying logged into a website in your normal browser.
# =============================================================================

import os
print("1. Loading Playwright libraries...")
from playwright.sync_api import sync_playwright

# Where the saved login will live: a folder called "copilot_browser_profile"
# in whatever directory this script happens to be run from.
USER_DATA_DIR = os.path.join(os.getcwd(), "copilot_browser_profile")
print(f"2. Target browser profile directory: {USER_DATA_DIR}")

# `sync_playwright()` starts up the automation engine. Everything inside this
# `with` block runs while that engine is alive; it shuts down cleanly when
# the block ends (including if something goes wrong partway through).
with sync_playwright() as p:
    print("3. Attempting to launch Microsoft Edge...")
    # `launch_persistent_context` is the key call: "persistent" means whatever
    # happens in this browser window (like logging in) gets saved to
    # USER_DATA_DIR and is still there the next time this folder is used.
    # headless=False means the browser window is actually shown on screen,
    # since a human needs to see it to type their login credentials.
    context = p.chromium.launch_persistent_context(
        user_data_dir=USER_DATA_DIR,
        channel="msedge",
        headless=False,
        args=["--disable-blink-features=AutomationControlled"]
    )
    print("4. Edge window open! Navigating to M365 Copilot Chat...")
    page = context.new_page()
    page.goto("https://m365.cloud.microsoft/chat/") # <-- Updated URL

    print("\n=== ACTION REQUIRED ===")
    print("-> Look at your desktop/taskbar for the new MS Edge window.")
    print("-> LOG IN to your enterprise M365 account inside THAT window.")
    print("-> Once you see your actual work chat layout, close the browser window.\n")

    # Keep the window open for up to 5 minutes so there's time to complete
    # login. Closing the Edge window yourself ends this early -- that's fine.
    page.wait_for_timeout(300000)
