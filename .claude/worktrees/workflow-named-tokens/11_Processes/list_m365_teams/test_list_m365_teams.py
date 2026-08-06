# =============================================================================
# test_list_m365_teams.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   Checks that list_m365_teams.py's `run()` returns a successful result
#   with at least one team, using the mock data m365_graph_bridge already
#   returns (no real Microsoft account needed).
#
# WHAT IT INTERACTS WITH
#   - `list_m365_teams.py`, the file under test.
# =============================================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from list_m365_teams import ListM365Teams


def test_run_returns_teams():
    result = ListM365Teams().run()
    assert result["success"] is True
    assert len(result["teams"]) >= 1


if __name__ == "__main__":
    test_run_returns_teams()
    print("All list_m365_teams self-checks passed.")
