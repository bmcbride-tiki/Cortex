import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "m365_graph_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from m365_graph_bridge import list_powerbi_reports as _list_powerbi_reports


class ListPowerbiReports:
    """Zero-input, click-and-run: lists reports in the default Power BI workspace.
    Reuses m365_graph_bridge's mock logic directly (no subprocess). Mock-mode until an
    Azure AD app registration exists."""

    def run(self) -> dict:
        try:
            return {"success": True, **_list_powerbi_reports()}
        except Exception as e:
            return {"success": False, "response": f"list_powerbi_reports error: {e}"}


if __name__ == "__main__":
    print(ListPowerbiReports().run())
