# =============================================================================
# image_description.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   A Task: generates a natural-language description of an image via Google
#   Gemini's multimodal input. Uses your signed-in Google session via
#   gemini_bridge.py (no API key) -- runs in mock mode by default
#   (GEMINI_MOCK_MODE) until a real session is configured. A missing
#   file_path fails clearly before ever reaching Gemini, rather than
#   surfacing as an opaque API error.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "gemini_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from gemini_bridge import ask_gemini as _ask_gemini


class ImageDescription:
    """Generates a natural-language description of an image via Gemini's
    multimodal input."""

    def run(self, file_path: str) -> dict:
        if not file_path:
            return {"success": False, "response": "file_path is required."}
        if not Path(file_path).exists():
            return {"success": False, "response": f"File not found: {file_path}"}
        prompt = "Describe this image in detailed, natural language."
        try:
            return {"success": True, "response": _ask_gemini(prompt, files=[file_path])}
        except Exception as e:
            return {"success": False, "response": f"image_description error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"file_path": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = ImageDescription().run(file_path=params.get("file_path", ""))
    except Exception as e:
        result = {"success": False, "response": f"image_description error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
