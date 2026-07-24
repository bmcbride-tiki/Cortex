import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "m365_graph_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from m365_graph_bridge import create_sharepoint_list_item as _create_sharepoint_list_item


class CreateSharepointListItem:
    """Adds a new item to a Microsoft List. Reuses m365_graph_bridge's mock logic
    directly (no subprocess). Mock-mode until an Azure AD app registration exists."""

    def run(self, site_id: str, list_id: str, fields: dict) -> dict:
        try:
            return {"success": True, **_create_sharepoint_list_item(site_id, list_id, fields)}
        except Exception as e:
            return {"success": False, "response": f"create_sharepoint_list_item error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"site_id": "...", "list_id": "...", "fields": {"Title": "..."}}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = CreateSharepointListItem().run(
            site_id=params.get("site_id", ""),
            list_id=params.get("list_id", ""),
            fields=params.get("fields", {}),
        )
    except Exception as e:
        result = {"success": False, "response": f"create_sharepoint_list_item error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
