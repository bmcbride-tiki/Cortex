# =============================================================================
# test_list_sharepoint_lists.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   Checks that list_sharepoint_lists.py's `run()` returns a successful
#   result with at least one list, using m365_graph_bridge's existing mock
#   data.
#
# WHAT IT INTERACTS WITH
#   - `list_sharepoint_lists.py`, the file under test.
# =============================================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from list_sharepoint_lists import ListSharepointLists


def test_run_returns_lists():
    result = ListSharepointLists().run("site_1")
    assert result["success"] is True
    assert len(result["lists"]) >= 1


if __name__ == "__main__":
    test_run_returns_lists()
    print("All list_sharepoint_lists self-checks passed.")
