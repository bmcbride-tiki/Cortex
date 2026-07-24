import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "m365_graph_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from m365_graph_bridge import list_onenote_pages as _list_onenote_pages


class ListOnenotePages:
    """Lists the pages in a OneNote notebook. Reuses m365_graph_bridge's mock logic
    directly (no subprocess). Mock-mode until an Azure AD app registration exists."""

    def run(self, notebook_id: str) -> dict:
        try:
            return {"success": True, **_list_onenote_pages(notebook_id)}
        except Exception as e:
            return {"success": False, "response": f"list_onenote_pages error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"notebook_id": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = ListOnenotePages().run(notebook_id=params.get("notebook_id", ""))
    except Exception as e:
        result = {"success": False, "response": f"list_onenote_pages error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
