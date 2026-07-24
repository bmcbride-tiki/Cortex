# =============================================================================
# upload_m365_file.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   A Task: uploads a local file to OneDrive/SharePoint.
#
# WHAT IT INTERACTS WITH
#   - `14_Adapters/m365_graph_bridge/m365_graph_bridge.py`'s
#     `upload_file()`, called directly in-process (no subprocess) --
#     validates the local file is real even in mock mode. Mock-mode until
#     a real Azure AD app registration exists.
#   - `test_upload_m365_file.py`, this file's paired test.
#   - `core_router.py`/`server.py`, which pass this Task its
#     `local_path`/`destination_path` as a JSON payload.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "m365_graph_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from m365_graph_bridge import upload_file


class UploadM365File:
    """Uploads a local file to OneDrive/SharePoint. Reuses m365_graph_bridge's mock
    logic directly (no subprocess), which still validates the local file is real even
    in mock mode. Mock-mode until an Azure AD app registration exists."""

    def run(self, local_path: str, destination_path: str) -> dict:
        try:
            return {"success": True, **upload_file(local_path, destination_path)}
        except Exception as e:
            return {"success": False, "response": f"upload_m365_file error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"local_path": "...", "destination_path": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = UploadM365File().run(local_path=params.get("local_path", ""), destination_path=params.get("destination_path", ""))
    except Exception as e:
        result = {"success": False, "response": f"upload_m365_file error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
