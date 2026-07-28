# =============================================================================
# ask_gemini.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   A Task: sends a prompt to Google Gemini and captures its response, or runs
#   it as a full Deep Research pass when search=True. Uses your signed-in
#   Google session via gemini_bridge.py (no API key) -- runs in mock mode by
#   default (GEMINI_MOCK_MODE) until a real session is configured.
#
# WHAT IT INTERACTS WITH
#   - `14_Adapters/gemini_bridge/gemini_bridge.py`'s `ask_gemini()`, called
#     directly in-process (no subprocess).
#   - `test_ask_gemini.py`, this file's paired test.
#   - `core_router.py`/`server.py`, which pass this Task its `prompt`/`search`
#     as a JSON payload.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "gemini_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from gemini_bridge import ask_gemini as _ask_gemini


class AskGemini:
    """Sends a prompt to Google Gemini and captures its response. Reuses
    gemini_bridge's ask_gemini() function directly (no subprocess) -- uses
    your signed-in Gemini session, or a mock response while GEMINI_MOCK_MODE
    is on (the default)."""

    def run(self, prompt: str, search: bool = False) -> dict:
        if not prompt:
            return {"success": False, "response": "A prompt is required."}
        try:
            return {"success": True, "response": _ask_gemini(prompt, use_search=search)}
        except Exception as e:
            return {"success": False, "response": f"ask_gemini error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"prompt": "...", "search": false}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = AskGemini().run(prompt=params.get("prompt", ""), search=bool(params.get("search", False)))
    except Exception as e:
        result = {"success": False, "response": f"ask_gemini error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
