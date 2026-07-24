# =============================================================================
# format_text_with_copilot.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   A Task: asks M365 Copilot to reformat/restyle a piece of text according
#   to free-text style notes (e.g. "format as a formal briefing note").
#
# WHAT IT INTERACTS WITH
#   - `14_Adapters/copilot_bridge/copilot_bridge.py`'s `ask_copilot()`,
#     called directly in-process (no subprocess) -- a real Playwright
#     browser-automation call against the signed-in Edge session, not a mock.
#   - `test_format_text_with_copilot.py`, this file's paired test.
#   - `core_router.py`/`server.py`, which pass this Task its
#     `text`/`style_notes` as a JSON payload.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "copilot_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from copilot_bridge import ask_copilot


class FormatTextWithCopilot:
    """Asks M365 Copilot to reformat/restyle text per style notes (e.g. into a formal
    briefing note). Reuses copilot_bridge's real browser-automation function directly
    (no subprocess) -- uses your signed-in Edge session, no API key."""

    def run(self, text: str, style_notes: str) -> dict:
        if not text:
            return {"success": False, "response": "text is required."}
        prompt = f"Reformat/restyle the following text.\nStyle notes: {style_notes}\n\nText:\n{text}"
        try:
            return {"success": True, "response": ask_copilot(prompt, headless=True)}
        except Exception as e:
            return {"success": False, "response": f"format_text_with_copilot error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"text": "...", "style_notes": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = FormatTextWithCopilot().run(text=params.get("text", ""), style_notes=params.get("style_notes", ""))
    except Exception as e:
        result = {"success": False, "response": f"format_text_with_copilot error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
