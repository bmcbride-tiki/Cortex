# =============================================================================
# ask_claude.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   A Task: sends a prompt to Anthropic Claude and captures its response.
#   Mock-mode until a real ANTHROPIC_API_KEY exists (see claude_bridge.py).
#
# WHAT IT INTERACTS WITH
#   - `14_Adapters/claude_bridge/claude_bridge.py`'s `ask()`, called directly
#     in-process (no subprocess).
#   - `test_ask_claude.py`, this file's paired test.
#   - `core_router.py`/`server.py`, which pass this Task its `prompt` as a
#     JSON payload.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "claude_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from claude_bridge import ask as _ask_claude


class AskClaude:
    """Sends a prompt to Anthropic Claude and captures its response. Reuses
    claude_bridge's ask() function directly (no subprocess) -- mock-mode
    until a real ANTHROPIC_API_KEY exists."""

    def run(self, prompt: str) -> dict:
        if not prompt:
            return {"success": False, "response": "A prompt is required."}
        try:
            return {"success": True, **_ask_claude(prompt)}
        except Exception as e:
            return {"success": False, "response": f"ask_claude error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"prompt": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = AskClaude().run(prompt=params.get("prompt", ""))
    except Exception as e:
        result = {"success": False, "response": f"ask_claude error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
