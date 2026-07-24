# =============================================================================
# test_list_onenote_notebooks.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   Checks that list_onenote_notebooks.py's `run()` returns a successful
#   result with at least one notebook, using the mock data
#   m365_graph_bridge already returns (no real Microsoft account needed).
#
# WHAT IT INTERACTS WITH
#   - `list_onenote_notebooks.py`, the file under test.
# =============================================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from list_onenote_notebooks import ListOnenoteNotebooks


def test_run_returns_notebooks():
    result = ListOnenoteNotebooks().run()
    assert result["success"] is True
    assert len(result["notebooks"]) >= 1


if __name__ == "__main__":
    test_run_returns_notebooks()
    print("All list_onenote_notebooks self-checks passed.")
