# =============================================================================
# run_copilot_test.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   A manual, one-off test script for the "upload a file to Copilot and ask
#   about it" feature. It is not part of the normal running system -- you'd
#   run this by hand from a terminal when you want to sanity-check that file
#   uploads still work, not something the Cortex web app or the workflow
#   builder calls automatically.
#
# WHAT IT INTERACTS WITH
#   - `copilot_ask.py` in this same folder, specifically its `CopilotBridge`
#     class, which is the older/experimental automation engine (see that
#     file's own notes for how it compares to `copilot_bridge.py`).
#   - A hard-coded test document at
#     C:\workbrain\02_vault\transcripts\copilot_test.docx
#     NOTE: as of this pass, the `02_vault/transcripts` folder has been
#     removed from the project, so this script will currently fail its
#     file-existence check and exit immediately. It's left in place as a
#     template for how to test uploads -- point TARGET_FILE at a real file
#     before running it again.
#   - Your saved Microsoft Edge login session (the same one `copilot_login.py`
#     sets up), via `CopilotBridge`.
#
# KEY FUNCTIONALITY NOTES
#   - Runs "headless" (headless=True), meaning no visible browser window
#     pops up -- the automation happens invisibly in the background. If you
#     want to watch it work, change that to headless=False.
#   - The test prompt asks Copilot to summarize whatever file gets uploaded,
#     which is a good quick check that both the file-attachment step and the
#     normal ask-and-read-the-answer step are functioning.
# =============================================================================

import os
import sys

# Make sure Python can find and import copilot_ask.py, which lives in this
# same folder. Without this, `from copilot_ask import CopilotBridge` below
# could fail depending on how this script is launched.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.append(SCRIPT_DIR)

# Import the new scalable CopilotBridge class
from copilot_ask import CopilotBridge

# Define paths and normalize for Windows.
# TARGET_FILE is the document that will be uploaded to Copilot as part of
# this test. Change RELATIVE_FILE_PATH if you want to test with a
# different file.
WORKBRAIN_ROOT = "C:\\workbrain"
RELATIVE_FILE_PATH = os.path.join("02_vault", "transcripts", "copilot_test.docx")
TARGET_FILE = os.path.normpath(os.path.join(WORKBRAIN_ROOT, RELATIVE_FILE_PATH))

def main():
    print("==================================================")
    print("      M365 COPILOT FILE UPLOAD TEST RUNNER        ")
    print("==================================================\n")

    # Verify that the test file actually exists. If it doesn't, there's no
    # point launching a whole browser automation session, so fail fast here.
    if not os.path.exists(TARGET_FILE):
        print(f"[ERROR] Target file not found at:\n  {TARGET_FILE}")
        sys.exit(1)

    print(f"Success! Verified local file exists:\n  {TARGET_FILE}\n")

    # 1. Initialize the new scalable class
    # Set headless=True to run in the background
    bot = CopilotBridge(profile_name="default", headless=True)

    test_prompt = (
        "Please analyze this uploaded document and write a quick 3-bullet-point summary "
        "explaining its main topics."
    )

    # 2. Run the prompt using the class method .ask()
    # This single call does everything: opens the browser, attaches
    # TARGET_FILE, types and submits test_prompt, waits for Copilot's answer
    # to finish streaming in, and returns it.
    result = bot.ask(
        prompt_text=test_prompt,
        file_to_upload=TARGET_FILE,
        expect_file_download=False
    )

    print("\n=== COPILOT SUMMARY RESPONSE ===")
    print(result["text"])
    print("=================================")

if __name__ == "__main__":
    main()
