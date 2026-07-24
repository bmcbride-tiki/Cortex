# =============================================================================
# list_teams_chat_messages.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   A Task: lists messages in a 1:1 or group Teams chat.
#
# WHAT IT INTERACTS WITH
#   - `14_Adapters/m365_graph_bridge/m365_graph_bridge.py`'s
#     `list_chat_messages()`, called directly in-process (no subprocess).
#     Mock-mode until a real Azure AD app registration exists.
#   - `test_list_teams_chat_messages.py`, this file's paired test.
#   - `core_router.py`/`server.py`, which pass this Task its `chat_id` as a
#     JSON payload.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "m365_graph_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from m365_graph_bridge import list_chat_messages


class ListTeamsChatMessages:
    """Lists messages in a 1:1 or group Teams chat. Reuses m365_graph_bridge's mock
    logic directly (no subprocess). Mock-mode until an Azure AD app registration
    exists."""

    def run(self, chat_id: str) -> dict:
        try:
            return {"success": True, **list_chat_messages(chat_id)}
        except Exception as e:
            return {"success": False, "response": f"list_teams_chat_messages error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"chat_id": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = ListTeamsChatMessages().run(chat_id=params.get("chat_id", ""))
    except Exception as e:
        result = {"success": False, "response": f"list_teams_chat_messages error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
