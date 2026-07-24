# =============================================================================
# test_list_m365_files.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   Checks that list_m365_files.py's `run()` returns a successful result
#   with at least one file, using m365_graph_bridge's existing mock data.
#
# WHAT IT INTERACTS WITH
#   - `list_m365_files.py`, the file under test.
# =============================================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from list_m365_files import ListM365Files


def test_run_returns_files():
    result = ListM365Files().run("/Reports")
    assert result["success"] is True
    assert len(result["files"]) >= 1


if __name__ == "__main__":
    test_run_returns_files()
    print("All list_m365_files self-checks passed.")
