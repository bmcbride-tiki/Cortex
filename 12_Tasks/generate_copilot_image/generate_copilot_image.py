# =============================================================================
# generate_copilot_image.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   A Task: asks M365 Copilot's Designer plugin to generate an image from a
#   prompt and saves it to a local folder.
#
# WHAT IT INTERACTS WITH
#   - `14_Adapters/copilot_bridge/copilot_bridge.py`'s `generate_image()`,
#     called directly in-process (no subprocess) -- a real Playwright
#     browser-automation call against the signed-in Edge session, not a mock.
#   - `test_generate_copilot_image.py`, this file's paired test.
#   - `core_router.py`/`server.py`, which pass this Task its
#     `prompt`/`output_dir` as a JSON payload.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "copilot_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from copilot_bridge import generate_image


class GenerateCopilotImage:
    """Asks the M365 Copilot bridge (Designer plugin) to generate an image and saves
    it to a local folder. Reuses copilot_bridge's real browser-automation function
    directly (no subprocess) -- uses your signed-in Edge session, no API key."""

    def run(self, prompt: str, output_dir: str) -> dict:
        if not prompt:
            return {"success": False, "response": "A prompt is required."}
        if not output_dir:
            return {"success": False, "response": "An output_dir is required."}
        try:
            return {"success": True, "file_path": generate_image(prompt, output_dir, headless=True)}
        except Exception as e:
            return {"success": False, "response": f"generate_copilot_image error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"prompt": "...", "output_dir": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = GenerateCopilotImage().run(prompt=params.get("prompt", ""), output_dir=params.get("output_dir", ""))
    except Exception as e:
        result = {"success": False, "response": f"generate_copilot_image error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
