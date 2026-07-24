# =============================================================================
# test_send_teams_chat_message.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   Checks that send_teams_chat_message.py's `run()` returns a successful,
#   "sent (mock)" result, using m365_graph_bridge's existing mock data.
#
# WHAT IT INTERACTS WITH
#   - `send_teams_chat_message.py`, the file under test.
# =============================================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from send_teams_chat_message import SendTeamsChatMessage


def test_run_sends_message():
    result = SendTeamsChatMessage().run("chat_1", "hi")
    assert result["success"] is True
    assert result["status"] == "sent (mock)"


if __name__ == "__main__":
    test_run_sends_message()
    print("All send_teams_chat_message self-checks passed.")
