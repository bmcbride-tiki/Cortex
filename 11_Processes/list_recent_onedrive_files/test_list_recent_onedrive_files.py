# =============================================================================
# test_list_recent_onedrive_files.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   Checks that list_recent_onedrive_files.py's `run()` returns a
#   successful result with at least one file, using the mock data
#   m365_graph_bridge already returns (no real Microsoft account needed).
#
# WHAT IT INTERACTS WITH
#   - `list_recent_onedrive_files.py`, the file under test.
# =============================================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from list_recent_onedrive_files import ListRecentOnedriveFiles


def test_run_returns_files():
    result = ListRecentOnedriveFiles().run()
    assert result["success"] is True
    assert len(result["files"]) >= 1


if __name__ == "__main__":
    test_run_returns_files()
    print("All list_recent_onedrive_files self-checks passed.")
