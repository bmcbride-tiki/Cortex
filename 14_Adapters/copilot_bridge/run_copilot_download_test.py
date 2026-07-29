# =============================================================================
# run_copilot_download_test.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   A manual, one-off test script for the "ask Copilot to generate a file and
#   download it automatically" feature. Like run_copilot_test.py, this is
#   meant to be run by hand from a terminal to sanity-check that behavior --
#   it is not called by the Cortex web app, the router, or the workflow
#   builder during normal operation.
#
# WHAT IT INTERACTS WITH
#   - `copilot_ask.py`'s `CopilotBridge` class in this same folder (the
#     older/experimental automation engine).
#   - Your saved Microsoft Edge login session, via CopilotBridge.
#   - The folder `C:\workbrain\02_vault\downloads\`, which is created
#     automatically if it doesn't already exist. Any file Copilot generates
#     and that this script manages to download gets saved there.
#
# KEY FUNCTIONALITY NOTES
#   - The test prompt specifically asks Copilot to produce a Word document
#     and to include a download/export link in its reply, since that link
#     is what the automation actually clicks to trigger a real file
#     download (Copilot won't hand over a file any other way).
#   - `expect_file_download=True` tells CopilotBridge to actively watch for
#     and capture that download after Copilot finishes responding; without
#     that flag, the class would only return the text of the answer.
#   - `timeout=180` gives Copilot up to 3 minutes to finish generating the
#     document before the script gives up -- document generation is slower
#     than a normal chat answer.
# =============================================================================

import os
import sys

# Make sure Python can find and import copilot_ask.py, which lives in this
# same folder.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.append(SCRIPT_DIR)

# Import the new scalable CopilotBridge class
from copilot_ask import CopilotBridge

# Define the target download folder inside our 02_vault. Any file Copilot
# generates during this test gets saved here.
WORKBRAIN_ROOT = "C:\\workbrain"
VAULT_DOWNLOADS_DIR = os.path.normpath(os.path.join(WORKBRAIN_ROOT, "02_vault", "downloads"))

def main():
    print("==================================================")
    print("     M365 COPILOT FILE GENERATOR & DOWNLOADER     ")
    print("==================================================\n")

    print(f"Target system download folder: {VAULT_DOWNLOADS_DIR}\n")

    # 1. Initialize the scalable class with our designated downloads directory
    bot = CopilotBridge(
        profile_name="default",
        headless=True,
        download_dir=VAULT_DOWNLOADS_DIR
    )

    # This prompt deliberately asks for a download/export link in the reply --
    # that link is what the automation looks for and clicks afterward to
    # actually pull the generated file onto this machine.
    download_prompt = (
        "Generate a Word document (.docx) listing all SharePoint Online sites "
        "I am connected with or have access to. Ensure you provide a direct download link "
        "or an export to OneDrive button in your final response so I can download it."
    )

    # 2. Run the prompt using the class method .ask()
    # expect_file_download=True tells CopilotBridge to look for and click a
    # download link in Copilot's answer, then save whatever file comes back.
    result = bot.ask(
        prompt_text=download_prompt,
        expect_file_download=True,
        timeout=180  # Max wait time of 3 minutes
    )

    print("\n=== COPILOT RESPONSE ===")
    print(result["text"])

    print("\n=== DOWNLOAD RESULTS ===")
    if result["downloaded_file"]:
        print(f"Success! The file was downloaded and saved at:")
        print(f"  {result['downloaded_file']}")
    else:
        print("Failure: No generated file was captured or downloaded.")
    print("=========================================")

if __name__ == "__main__":
    main()
