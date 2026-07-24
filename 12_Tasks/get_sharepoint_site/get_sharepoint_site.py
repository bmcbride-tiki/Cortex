import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "m365_graph_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from m365_graph_bridge import get_sharepoint_site as _get_sharepoint_site


class GetSharepointSite:
    """Gets a specific SharePoint Online site's details. Reuses m365_graph_bridge's
    mock logic directly (no subprocess). Mock-mode until an Azure AD app registration
    exists."""

    def run(self, site_path: str) -> dict:
        try:
            return {"success": True, **_get_sharepoint_site(site_path)}
        except Exception as e:
            return {"success": False, "response": f"get_sharepoint_site error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"site_path": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = GetSharepointSite().run(site_path=params.get("site_path", ""))
    except Exception as e:
        result = {"success": False, "response": f"get_sharepoint_site error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
