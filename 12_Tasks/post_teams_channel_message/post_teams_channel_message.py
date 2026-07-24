import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "m365_graph_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from m365_graph_bridge import post_channel_message


class PostTeamsChannelMessage:
    """Posts a message to a Teams channel. Reuses m365_graph_bridge's mock logic
    directly (no subprocess). Mock-mode until an Azure AD app registration exists."""

    def run(self, team_id: str, channel_id: str, message: str) -> dict:
        try:
            return {"success": True, **post_channel_message(team_id, channel_id, message)}
        except Exception as e:
            return {"success": False, "response": f"post_teams_channel_message error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"team_id": "...", "channel_id": "...", "message": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = PostTeamsChannelMessage().run(
            team_id=params.get("team_id", ""),
            channel_id=params.get("channel_id", ""),
            message=params.get("message", ""),
        )
    except Exception as e:
        result = {"success": False, "response": f"post_teams_channel_message error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
