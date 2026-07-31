# =============================================================================
# key_phrase_extraction.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   A Task: extracts the main key phrases/topics from a body of text via
#   Google Gemini, as a JSON array of strings -- composes directly with the
#   Workflow Builder's Parse JSON / array-op Function nodes. Uses your
#   signed-in Google session via gemini_bridge.py (no API key) -- runs in
#   mock mode by default (GEMINI_MOCK_MODE) until a real session is
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


class KeyPhraseExtraction:
    """Extracts key phrases/topics from a body of text via Gemini, as a JSON
    array of strings. `language` is an optional hint, not a hard requirement."""

    def run(self, text: str, language: str = "") -> dict:
        if not text:
            return {"success": False, "response": "text is required."}
        lang_note = f" (the text is in {language})" if language else ""
        prompt = (
            f"Extract the main key phrases/topics from the following text{lang_note}. "
            f"Reply as a JSON array of strings only, no other text.\n\nText:\n{text}"
        )
        try:
            return {"success": True, "response": _ask_gemini(prompt)}
        except Exception as e:
            return {"success": False, "response": f"key_phrase_extraction error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"text": "...", "language": ""}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = KeyPhraseExtraction().run(text=params.get("text", ""), language=params.get("language", ""))
    except Exception as e:
        result = {"success": False, "response": f"key_phrase_extraction error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
