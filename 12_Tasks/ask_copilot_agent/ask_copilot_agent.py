# Copyright 2025 Brian McBride at Tiki-1 Studio
import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "copilot_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from copilot_bridge import ask_agent


class AskCopilotAgent:
    """Grounds a message to a specific @-mentioned M365 Copilot agent (e.g.
    Hal-9000) and captures its response. Reuses copilot_bridge's real
    browser-automation function directly (no subprocess) -- uses your signed-in Edge
    session, no API key. Get agent names from [[list_copilot_agents]]."""

    def run(self, agent_name: str, prompt: str) -> dict:
        if not agent_name:
            return {"success": False, "response": "An agent_name is required."}
        if not prompt:
            return {"success": False, "response": "A prompt is required."}
        try:
            return {"success": True, "response": ask_agent(agent_name, prompt, headless=True)}
        except Exception as e:
            return {"success": False, "response": f"ask_copilot_agent error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"agent_name": "...", "prompt": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = AskCopilotAgent().run(agent_name=params.get("agent_name", ""), prompt=params.get("prompt", ""))
    except Exception as e:
        result = {"success": False, "response": f"ask_copilot_agent error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
