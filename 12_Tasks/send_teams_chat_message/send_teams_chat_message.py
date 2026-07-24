# =============================================================================
# send_teams_chat_message.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   A Task: sends a message in a 1:1 or group Teams chat.
#
# WHAT IT INTERACTS WITH
#   - `14_Adapters/m365_graph_bridge/m365_graph_bridge.py`'s
#     `send_chat_message()`, called directly in-process (no subprocess).
#     Mock-mode until a real Azure AD app registration exists.
#   - `test_send_teams_chat_message.py`, this file's paired test.
#   - `core_router.py`/`server.py`, which pass this Task its
#     `chat_id`/`message` as a JSON payload.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "m365_graph_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from m365_graph_bridge import send_chat_message


class SendTeamsChatMessage:
    """Sends a message in a 1:1 or group Teams chat. Reuses m365_graph_bridge's mock
    logic directly (no subprocess). Mock-mode until an Azure AD app registration
    exists."""

    def run(self, chat_id: str, message: str) -> dict:
        try:
            return {"success": True, **send_chat_message(chat_id, message)}
        except Exception as e:
            return {"success": False, "response": f"send_teams_chat_message error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"chat_id": "...", "message": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = SendTeamsChatMessage().run(chat_id=params.get("chat_id", ""), message=params.get("message", ""))
    except Exception as e:
        result = {"success": False, "response": f"send_teams_chat_message error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
