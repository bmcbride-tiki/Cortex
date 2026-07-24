# =============================================================================
# test_get_onenote_page_content.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   Checks that get_onenote_page_content.py's `run()` returns a successful
#   result containing HTML content, using m365_graph_bridge's existing
#   mock data.
#
# WHAT IT INTERACTS WITH
#   - `get_onenote_page_content.py`, the file under test.
# =============================================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from get_onenote_page_content import GetOnenotePageContent


def test_run_returns_html():
    result = GetOnenotePageContent().run("page_1")
    assert result["success"] is True
    assert "<html>" in result["content_html"]


if __name__ == "__main__":
    test_run_returns_html()
    print("All get_onenote_page_content self-checks passed.")
