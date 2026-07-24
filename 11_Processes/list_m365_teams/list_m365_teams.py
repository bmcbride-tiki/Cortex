import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "m365_graph_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from m365_graph_bridge import list_teams


class ListM365Teams:
    """Zero-input, click-and-run: lists the Teams the signed-in M365 user belongs to.
    Reuses m365_graph_bridge's mock logic directly (no subprocess) since it's the same
    Python environment. Mock-mode until an Azure AD app registration exists."""

    def run(self) -> dict:
        try:
            return {"success": True, **list_teams()}
        except Exception as e:
            return {"success": False, "response": f"list_m365_teams error: {e}"}


if __name__ == "__main__":
    print(ListM365Teams().run())
