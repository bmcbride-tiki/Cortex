# =============================================================================
# list_copilot_agents.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   A zero-input, one-click Process: lists the agents available to
#   @-mention in Microsoft 365 Copilot chat (name + description).
#
# WHAT IT INTERACTS WITH
#   - `14_Adapters/copilot_bridge/copilot_bridge.py`'s `list_agents()`,
#     called directly in-process (no subprocess) -- a real Playwright
#     browser-automation call against the signed-in Edge session, not a
#     mock. Requires a completed "Initialize Session Auth" run first.
#   - `test_list_copilot_agents.py`, this file's paired test.
#   - `core_router.py`, which discovers and launches this script the same
#     way as every other Process.
# =============================================================================

import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "copilot_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from copilot_bridge import list_agents


class ListCopilotAgents:
    """Zero-input, click-and-run: lists the agents available to @-mention in M365
    Copilot chat. Reuses copilot_bridge's real browser-automation function directly
    (no subprocess) -- uses your signed-in Edge session, no API key. Requires a
    completed 'Initialize Session Auth' run first (see copilot_bridge.md)."""

    def run(self) -> dict:
        try:
            return {"success": True, "agents": list_agents(headless=True)}
        except Exception as e:
            return {"success": False, "response": f"list_copilot_agents error: {e}"}


if __name__ == "__main__":
    print(ListCopilotAgents().run())
