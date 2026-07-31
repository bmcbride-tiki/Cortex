# =============================================================================
# summarize_text.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   A Task: summarizes a body of text via Google Gemini. Uses your signed-in
#   Google session via gemini_bridge.py (no API key) -- runs in mock mode by
#   default (GEMINI_MOCK_MODE) until a real session is configured.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "gemini_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from gemini_bridge import ask_gemini as _ask_gemini


class SummarizeText:
    """Summarizes a body of text via Gemini, capturing the key points concisely."""

    def run(self, text_content: str) -> dict:
        if not text_content:
            return {"success": False, "response": "text_content is required."}
        prompt = f"Summarize the following text concisely, capturing the key points:\n\n{text_content}"
        try:
            return {"success": True, "response": _ask_gemini(prompt)}
        except Exception as e:
            return {"success": False, "response": f"summarize_text error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"text_content": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = SummarizeText().run(text_content=params.get("text_content", ""))
    except Exception as e:
        result = {"success": False, "response": f"summarize_text error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
