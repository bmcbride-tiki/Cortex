import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "m365_graph_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from m365_graph_bridge import list_sharepoint_sites as _list_sharepoint_sites


class ListSharepointSites:
    """Zero-input, click-and-run: lists SharePoint Online sites. Reuses
    m365_graph_bridge's mock logic directly (no subprocess). Mock-mode until an Azure
    AD app registration exists."""

    def run(self) -> dict:
        try:
            return {"success": True, **_list_sharepoint_sites()}
        except Exception as e:
            return {"success": False, "response": f"list_sharepoint_sites error: {e}"}


if __name__ == "__main__":
    print(ListSharepointSites().run())
