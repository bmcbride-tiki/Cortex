import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "m365_graph_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from m365_graph_bridge import list_sharepoint_lists as _list_sharepoint_lists


class ListSharepointLists:
    """Lists a SharePoint site's Microsoft Lists. Reuses m365_graph_bridge's mock
    logic directly (no subprocess). Mock-mode until an Azure AD app registration
    exists."""

    def run(self, site_id: str) -> dict:
        try:
            return {"success": True, **_list_sharepoint_lists(site_id)}
        except Exception as e:
            return {"success": False, "response": f"list_sharepoint_lists error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"site_id": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = ListSharepointLists().run(site_id=params.get("site_id", ""))
    except Exception as e:
        result = {"success": False, "response": f"list_sharepoint_lists error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
