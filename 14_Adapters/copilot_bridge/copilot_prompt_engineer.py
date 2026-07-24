# =============================================================================
# copilot_prompt_engineer.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   A small command-line helper for manually testing one specific way of
#   opening Copilot chat: by baking your question directly into the web
#   address (URL) itself, instead of typing it into the chat box after the
#   page loads. You run this from a terminal, type or paste in a question,
#   and it builds the special URL, prints it, then opens it in an automated
#   browser and prints back Copilot's answer.
#
# WHAT IT INTERACTS WITH
#   - `copilot_ask.py`'s `ask_copilot(...)` function in this same folder,
#     which does the actual browser automation once the URL is built.
#   - Your saved Microsoft Edge login session (via ask_copilot).
#   - m365.cloud.microsoft (Microsoft's Copilot chat website), reached
#     through a specially constructed link like:
#       https://m365.cloud.microsoft/chat/?q=your+question+here
#
# KEY FUNCTIONALITY NOTES
#   - "URL-encoding" (via `urllib.parse.quote`) is the step that turns plain
#     text like "what's on my plate today?" into a form that's safe to put
#     inside a web address -- spaces, question marks, and other special
#     characters get replaced with escape codes so the browser doesn't
#     misread them as part of the address structure instead of your text.
#   - This runs with headless=False, meaning a real, visible Edge window
#     pops up so you can watch the automation happen -- useful specifically
#     for confirming the URL-based approach actually pre-fills the chat box
#     the way you'd expect.
#   - This is a diagnostic/manual tool, not something the Cortex web app or
#     router calls -- `copilot_bridge.py` (the production adapter) submits
#     prompts by typing into the chat box directly rather than building a
#     URL, so this file mainly exists to test that the URL-parameter
#     approach still works as an alternative.
# =============================================================================

import os
import sys
import urllib.parse

# Import our core ask function from our sibling file
from copilot_ask import ask_copilot


def generate_copilot_url(prompt_text: str) -> str:
    """Safely URL-encodes the prompt and appends it as a 'q' query parameter

    to the M365 Copilot URL.
    """
    # Safe encoding (replaces spaces with %20, handles special characters).
    # Without this step, a prompt containing spaces or symbols like "&" or
    # "?" could break the web address or get cut off partway through.
    encoded_prompt = urllib.parse.quote(prompt_text)

    # We construct the URL targeting M365 Copilot Chat. Adding "?q=<prompt>"
    # is a convention this site supports for pre-filling the chat box with
    # a starting question when the page first loads.
    base_url = "https://m365.cloud.microsoft/chat/"
    constructed_url = f"{base_url}?q={encoded_prompt}"

    return constructed_url


def main():
    print("=========================================")
    print("   M365 COPILOT PROMPT ENGINEER TOOL     ")
    print("=========================================\n")

    # 1. Grab the prompt from CLI arguments if provided, otherwise ask via input.
    # This means you can either run:
    #   python copilot_prompt_engineer.py what is the weather today
    # or just run the script with no arguments and it will prompt you to type
    # a question interactively.
    if len(sys.argv) > 1:
        # Join all arguments passed after the script name
        user_prompt = " ".join(sys.argv[1:])
    else:
        user_prompt = input("Enter your Copilot prompt: ").strip()

    if not user_prompt:
        print("Error: Prompt cannot be empty.")
        sys.exit(1)

    # 2. Build the URL
    copilot_url = generate_copilot_url(user_prompt)

    print("\n--- Generated URL ---")
    print(copilot_url)
    print("---------------------\n")

    # 3. Pass the generated URL directly to the automation bridge to run it.
    # headless=False means a visible browser window will open so you can
    # watch this happen in real time.
    print("Handoff to Copilot automation bridge starting...")
    response = ask_copilot(target_url=copilot_url, headless=False)

    print("\n=== COPILOT RESPONSE ===")
    print(response)


if __name__ == "__main__":
    main()
