import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "copilot_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from copilot_bridge import ask_copilot as _ask_copilot


class AskCopilot:
    """Sends a prompt to M365 Copilot and captures its response. Reuses
    copilot_bridge's real browser-automation function directly (no subprocess) --
    uses your signed-in Edge session, no API key. Requires a completed 'Initialize
    Session Auth' run first (see copilot_bridge.md)."""

    def run(self, prompt: str) -> dict:
        if not prompt:
            return {"success": False, "response": "A prompt is required."}
        try:
            return {"success": True, "response": _ask_copilot(prompt, headless=True)}
        except Exception as e:
            return {"success": False, "response": f"ask_copilot error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"prompt": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = AskCopilot().run(prompt=params.get("prompt", ""))
    except Exception as e:
        result = {"success": False, "response": f"ask_copilot error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
