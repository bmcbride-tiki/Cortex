# =============================================================================
# test_list_sharepoint_sites.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   Checks that list_sharepoint_sites.py's `run()` returns a successful
#   result with at least one site, using the mock data m365_graph_bridge
#   already returns (no real Microsoft account needed).
#
# WHAT IT INTERACTS WITH
#   - `list_sharepoint_sites.py`, the file under test.
# =============================================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from list_sharepoint_sites import ListSharepointSites


def test_run_returns_sites():
    result = ListSharepointSites().run()
    assert result["success"] is True
    assert len(result["sites"]) >= 1


if __name__ == "__main__":
    test_run_returns_sites()
    print("All list_sharepoint_sites self-checks passed.")
