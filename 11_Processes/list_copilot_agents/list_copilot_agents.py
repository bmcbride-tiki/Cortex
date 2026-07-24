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
