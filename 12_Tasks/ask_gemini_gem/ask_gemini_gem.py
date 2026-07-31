# =============================================================================
# ask_gemini_gem.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   A Task: grounds a message to a specific named Gemini Gem (custom
#   instructions + dataset loaded via the Gem interface) and captures its
#   response. Gemini's equivalent of ask_copilot_agent.
#
# WHAT IT INTERACTS WITH
#   - `14_Adapters/gemini_bridge/gemini_bridge.py`'s `ask_gemini_gem()`,
#     called directly in-process (no subprocess). Runs in mock mode by
#     default (GEMINI_MOCK_MODE) until a real signed-in session is
#     configured.
#   - `test_ask_gemini_gem.py`, this file's paired test.
#   - `core_router.py`/`server.py`, which pass this Task its `gem_name`/
#     `prompt` as a JSON payload.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "gemini_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from gemini_bridge import ask_gemini_gem as _ask_gemini_gem


class AskGeminiGem:
    """Grounds a message to a specific named Gemini Gem and captures its response.
    Reuses gemini_bridge's ask_gemini_gem() directly (no subprocess) -- your
    signed-in Google session, no API key, when not in mock mode. Get gem names
    from [[list_gems]]."""

    def run(self, gem_name: str, prompt: str) -> dict:
        if not gem_name:
            return {"success": False, "response": "A gem_name is required."}
        if not prompt:
            return {"success": False, "response": "A prompt is required."}
        try:
            return {"success": True, "response": _ask_gemini_gem(gem_name, prompt)}
        except Exception as e:
            return {"success": False, "response": f"ask_gemini_gem error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"gem_name": "...", "prompt": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = AskGeminiGem().run(gem_name=params.get("gem_name", ""), prompt=params.get("prompt", ""))
    except Exception as e:
        result = {"success": False, "response": f"ask_gemini_gem error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
