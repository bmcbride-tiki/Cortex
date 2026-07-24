# =============================================================================
# test_list_sharepoint_list_items.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   Checks that list_sharepoint_list_items.py's `run()` returns a
#   successful result with at least one item, using m365_graph_bridge's
#   existing mock data.
#
# WHAT IT INTERACTS WITH
#   - `list_sharepoint_list_items.py`, the file under test.
# =============================================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from list_sharepoint_list_items import ListSharepointListItems


def test_run_returns_items():
    result = ListSharepointListItems().run("site_1", "list_1")
    assert result["success"] is True
    assert len(result["items"]) >= 1


if __name__ == "__main__":
    test_run_returns_items()
    print("All list_sharepoint_list_items self-checks passed.")
