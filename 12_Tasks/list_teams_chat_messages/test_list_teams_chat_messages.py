# =============================================================================
# test_list_teams_chat_messages.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   Checks that list_teams_chat_messages.py's `run()` returns a successful
#   result with at least one message, using m365_graph_bridge's existing
#   mock data.
#
# WHAT IT INTERACTS WITH
#   - `list_teams_chat_messages.py`, the file under test.
# =============================================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from list_teams_chat_messages import ListTeamsChatMessages


def test_run_returns_messages():
    result = ListTeamsChatMessages().run("chat_1")
    assert result["success"] is True
    assert len(result["messages"]) >= 1


if __name__ == "__main__":
    test_run_returns_messages()
    print("All list_teams_chat_messages self-checks passed.")
