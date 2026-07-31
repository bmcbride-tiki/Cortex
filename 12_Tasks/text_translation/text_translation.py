# =============================================================================
# text_translation.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   A Task: translates a body of text to a target language via Google Gemini.
#   Uses your signed-in Google session via gemini_bridge.py (no API key) --
#   runs in mock mode by default (GEMINI_MOCK_MODE) until a real session is
#   configured.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "gemini_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from gemini_bridge import ask_gemini as _ask_gemini


class TextTranslation:
    """Translates a body of text to a target language via Gemini. `source_language`
    is optional -- Gemini detects the source language on its own when omitted."""

    def run(self, text: str, target_language: str, source_language: str = "") -> dict:
        if not text:
            return {"success": False, "response": "text is required."}
        if not target_language:
            return {"success": False, "response": "target_language is required."}
        source_note = f" (source language: {source_language})" if source_language else ""
        prompt = (
            f"Translate the following text to {target_language}{source_note}. "
            f"Reply with only the translated text, no explanation.\n\nText:\n{text}"
        )
        try:
            return {"success": True, "response": _ask_gemini(prompt)}
        except Exception as e:
            return {"success": False, "response": f"text_translation error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"text": "...", "target_language": "...", "source_language": ""}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = TextTranslation().run(
            text=params.get("text", ""),
            target_language=params.get("target_language", ""),
            source_language=params.get("source_language", ""),
        )
    except Exception as e:
        result = {"success": False, "response": f"text_translation error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
