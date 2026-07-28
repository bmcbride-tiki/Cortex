# =============================================================================
# generate_gemini_image.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   A Task: asks Google Gemini's built-in image generation to create an image
#   from a prompt and saves it to a local folder. Runs in mock mode by
#   default (GEMINI_MOCK_MODE) until a real session is configured.
#
# WHAT IT INTERACTS WITH
#   - `14_Adapters/gemini_bridge/gemini_bridge.py`'s `generate_image()`,
#     called directly in-process (no subprocess).
#   - `test_generate_gemini_image.py`, this file's paired test.
#   - `core_router.py`/`server.py`, which pass this Task its
#     `prompt`/`output_dir` as a JSON payload.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "gemini_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from gemini_bridge import generate_image as _generate_image


class GenerateGeminiImage:
    """Asks the Gemini bridge to generate an image and saves it to a local
    folder. Reuses gemini_bridge's generate_image() function directly (no
    subprocess) -- uses your signed-in Gemini session, or a mock placeholder
    file while GEMINI_MOCK_MODE is on (the default)."""

    def run(self, prompt: str, output_dir: str) -> dict:
        if not prompt:
            return {"success": False, "response": "A prompt is required."}
        if not output_dir:
            return {"success": False, "response": "An output_dir is required."}
        try:
            return {"success": True, "file_path": _generate_image(prompt, output_dir)}
        except Exception as e:
            return {"success": False, "response": f"generate_gemini_image error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"prompt": "...", "output_dir": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = GenerateGeminiImage().run(prompt=params.get("prompt", ""), output_dir=params.get("output_dir", ""))
    except Exception as e:
        result = {"success": False, "response": f"generate_gemini_image error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
