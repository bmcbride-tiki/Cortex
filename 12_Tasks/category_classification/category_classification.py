# =============================================================================
# category_classification.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   A Task: classifies a body of text into one of a given set of categories,
#   via Google Gemini. `categories` replaces the original spec's opaque
#   "Model" parameter -- there is no trained classifier here, just an
#   instruction naming the allowed categories. Uses your signed-in Google
#   session via gemini_bridge.py (no API key) -- runs in mock mode by default
#   (GEMINI_MOCK_MODE) until a real session is configured.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "gemini_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from gemini_bridge import ask_gemini as _ask_gemini


class CategoryClassification:
    """Classifies a body of text into exactly one of a comma-separated list
    of categories, via Gemini."""

    def run(self, text: str, categories: str) -> dict:
        if not text:
            return {"success": False, "response": "text is required."}
        if not categories:
            return {"success": False, "response": "categories is required (comma-separated list)."}
        prompt = (
            f"Classify the following text into exactly one of these categories: {categories}. "
            f"Reply with just the category name, no other text.\n\nText:\n{text}"
        )
        try:
            return {"success": True, "response": _ask_gemini(prompt)}
        except Exception as e:
            return {"success": False, "response": f"category_classification error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"text": "...", "categories": "A, B, C"}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = CategoryClassification().run(text=params.get("text", ""), categories=params.get("categories", ""))
    except Exception as e:
        result = {"success": False, "response": f"category_classification error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
