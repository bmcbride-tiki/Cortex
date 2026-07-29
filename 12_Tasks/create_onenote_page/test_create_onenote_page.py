# =============================================================================
# test_create_onenote_page.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   Checks that create_onenote_page.py's `run()` returns a successful
#   result with a real-looking page ID, using m365_graph_bridge's existing
#   mock data.
#
# WHAT IT INTERACTS WITH
#   - `create_onenote_page.py`, the file under test.
# =============================================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from create_onenote_page import CreateOnenotePage


def test_run_creates_page():
    result = CreateOnenotePage().run("section_1", "New Page", "<p>Body</p>")
    assert result["success"] is True
    assert result["page_id"].startswith("page_")


if __name__ == "__main__":
    test_run_creates_page()
    print("All create_onenote_page self-checks passed.")
