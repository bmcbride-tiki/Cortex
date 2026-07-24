# =============================================================================
# test_create_sharepoint_list_item.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   Checks that create_sharepoint_list_item.py's `run()` returns a
#   successful result with a real-looking item ID, using
#   m365_graph_bridge's existing mock data.
#
# WHAT IT INTERACTS WITH
#   - `create_sharepoint_list_item.py`, the file under test.
# =============================================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from create_sharepoint_list_item import CreateSharepointListItem


def test_run_creates_item():
    result = CreateSharepointListItem().run("site_1", "list_1", {"Title": "New Item"})
    assert result["success"] is True
    assert result["item_id"].startswith("item_")


if __name__ == "__main__":
    test_run_creates_item()
    print("All create_sharepoint_list_item self-checks passed.")
