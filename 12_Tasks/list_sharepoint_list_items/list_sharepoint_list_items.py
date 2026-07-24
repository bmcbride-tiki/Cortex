# =============================================================================
# list_sharepoint_list_items.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   A Task: gets a Microsoft List's items, each with a `fields` object of
#   column values.
#
# WHAT IT INTERACTS WITH
#   - `14_Adapters/m365_graph_bridge/m365_graph_bridge.py`'s
#     `list_sharepoint_list_items()`, called directly in-process (no
#     subprocess). Mock-mode until a real Azure AD app registration exists.
#   - `test_list_sharepoint_list_items.py`, this file's paired test.
#   - `core_router.py`/`server.py`, which pass this Task its
#     `site_id`/`list_id` as a JSON payload.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "m365_graph_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from m365_graph_bridge import list_sharepoint_list_items as _list_sharepoint_list_items


class ListSharepointListItems:
    """Gets a Microsoft List's items (each with a fields object of column values).
    Reuses m365_graph_bridge's mock logic directly (no subprocess). Mock-mode until an
    Azure AD app registration exists."""

    def run(self, site_id: str, list_id: str) -> dict:
        try:
            return {"success": True, **_list_sharepoint_list_items(site_id, list_id)}
        except Exception as e:
            return {"success": False, "response": f"list_sharepoint_list_items error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"site_id": "...", "list_id": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = ListSharepointListItems().run(site_id=params.get("site_id", ""), list_id=params.get("list_id", ""))
    except Exception as e:
        result = {"success": False, "response": f"list_sharepoint_list_items error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
