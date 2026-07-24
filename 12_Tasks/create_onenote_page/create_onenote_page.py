# =============================================================================
# create_onenote_page.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   A Task: creates a new OneNote page (with a title and HTML content) in a
#   given section.
#
# WHAT IT INTERACTS WITH
#   - `14_Adapters/m365_graph_bridge/m365_graph_bridge.py`'s
#     `create_onenote_page()`, called directly in-process (no subprocess).
#     Mock-mode until a real Azure AD app registration exists.
#   - `test_create_onenote_page.py`, this file's paired test.
#   - `core_router.py`/`server.py`, which pass this Task its
#     `section_id`/`title`/`content` arguments as a JSON payload.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "m365_graph_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from m365_graph_bridge import create_onenote_page as _create_onenote_page


class CreateOnenotePage:
    """Creates a new OneNote page in a section. Reuses m365_graph_bridge's mock logic
    directly (no subprocess). Mock-mode until an Azure AD app registration exists."""

    def run(self, section_id: str, title: str, content: str) -> dict:
        try:
            return {"success": True, **_create_onenote_page(section_id, title, content)}
        except Exception as e:
            return {"success": False, "response": f"create_onenote_page error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"section_id": "...", "title": "...", "content": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = CreateOnenotePage().run(
            section_id=params.get("section_id", ""),
            title=params.get("title", ""),
            content=params.get("content", ""),
        )
    except Exception as e:
        result = {"success": False, "response": f"create_onenote_page error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
