# =============================================================================
# sentiment_analysis.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   A Task: judges the sentiment (Positive/Negative/Neutral) of a body of text
#   via Google Gemini. Uses your signed-in Google session via gemini_bridge.py
#   (no API key) -- runs in mock mode by default (GEMINI_MOCK_MODE) until a
#   real session is configured.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "gemini_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from gemini_bridge import ask_gemini as _ask_gemini


class SentimentAnalysis:
    """Analyzes the sentiment of a body of text via Gemini. `language` is an
    optional hint, not a hard requirement -- Gemini detects language on its own."""

    def run(self, text: str, language: str = "") -> dict:
        if not text:
            return {"success": False, "response": "text is required."}
        lang_note = f" (the text is in {language})" if language else ""
        prompt = (
            f"Analyze the sentiment of the following text{lang_note}. Reply with exactly "
            f"one word (Positive, Negative, or Neutral) followed by a one-sentence explanation.\n\n"
            f"Text:\n{text}"
        )
        try:
            return {"success": True, "response": _ask_gemini(prompt)}
        except Exception as e:
            return {"success": False, "response": f"sentiment_analysis error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"text": "...", "language": ""}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = SentimentAnalysis().run(text=params.get("text", ""), language=params.get("language", ""))
    except Exception as e:
        result = {"success": False, "response": f"sentiment_analysis error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
