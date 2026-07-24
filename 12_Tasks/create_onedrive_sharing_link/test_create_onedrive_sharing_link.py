# =============================================================================
# test_create_onedrive_sharing_link.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   Checks that create_onedrive_sharing_link.py's `run()` returns a
#   successful result with a real-looking share URL, using
#   m365_graph_bridge's existing mock data.
#
# WHAT IT INTERACTS WITH
#   - `create_onedrive_sharing_link.py`, the file under test.
# =============================================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from create_onedrive_sharing_link import CreateOnedriveSharingLink


def test_run_creates_link():
    result = CreateOnedriveSharingLink().run("/Reports/Budget.xlsx")
    assert result["success"] is True
    assert result["share_url"].startswith("https://")


if __name__ == "__main__":
    test_run_creates_link()
    print("All create_onedrive_sharing_link self-checks passed.")
