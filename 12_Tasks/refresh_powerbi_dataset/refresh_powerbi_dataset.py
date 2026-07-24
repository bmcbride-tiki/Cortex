import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "m365_graph_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from m365_graph_bridge import refresh_powerbi_dataset as _refresh_powerbi_dataset


class RefreshPowerbiDataset:
    """Triggers a Power BI dataset refresh -- the real way to run a Power Query
    transformation programmatically (Power Query itself has no standalone API). Reuses
    m365_graph_bridge's mock logic directly (no subprocess). Mock-mode until an Azure
    AD app registration exists."""

    def run(self, dataset_id: str) -> dict:
        try:
            return {"success": True, **_refresh_powerbi_dataset(dataset_id)}
        except Exception as e:
            return {"success": False, "response": f"refresh_powerbi_dataset error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"dataset_id": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = RefreshPowerbiDataset().run(dataset_id=params.get("dataset_id", ""))
    except Exception as e:
        result = {"success": False, "response": f"refresh_powerbi_dataset error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
