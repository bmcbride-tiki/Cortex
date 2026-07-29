# =============================================================================
# get_onenote_page_content.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   A Task: gets a OneNote page's content as HTML (Graph's real OneNote
#   pages are HTML-based, not plain text).
#
# WHAT IT INTERACTS WITH
#   - `14_Adapters/m365_graph_bridge/m365_graph_bridge.py`'s
#     `get_onenote_page_content()`, called directly in-process (no
#     subprocess). Mock-mode until a real Azure AD app registration exists.
#   - `test_get_onenote_page_content.py`, this file's paired test.
#   - `core_router.py`/`server.py`, which pass this Task its `page_id` as a
#     JSON payload.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "m365_graph_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from m365_graph_bridge import get_onenote_page_content as _get_onenote_page_content


class GetOnenotePageContent:
    """Gets a OneNote page's content as HTML (Graph's real OneNote pages are
    HTML-based). Reuses m365_graph_bridge's mock logic directly (no subprocess).
    Mock-mode until an Azure AD app registration exists."""

    def run(self, page_id: str) -> dict:
        try:
            return {"success": True, **_get_onenote_page_content(page_id)}
        except Exception as e:
            return {"success": False, "response": f"get_onenote_page_content error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"page_id": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = GetOnenotePageContent().run(page_id=params.get("page_id", ""))
    except Exception as e:
        result = {"success": False, "response": f"get_onenote_page_content error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
