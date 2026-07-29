# =============================================================================
# list_m365_files.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   A Task: lists files in a given OneDrive/SharePoint folder path.
#
# WHAT IT INTERACTS WITH
#   - `14_Adapters/m365_graph_bridge/m365_graph_bridge.py`'s `list_files()`,
#     called directly in-process (no subprocess). Mock-mode until a real
#     Azure AD app registration exists.
#   - `test_list_m365_files.py`, this file's paired test.
#   - `core_router.py`/`server.py`, which pass this Task its `folder_path`
#     as a JSON payload.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "m365_graph_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from m365_graph_bridge import list_files


class ListM365Files:
    """Lists files in a OneDrive/SharePoint folder. Reuses m365_graph_bridge's mock
    logic directly (no subprocess). Mock-mode until an Azure AD app registration
    exists."""

    def run(self, folder_path: str) -> dict:
        try:
            return {"success": True, **list_files(folder_path)}
        except Exception as e:
            return {"success": False, "response": f"list_m365_files error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"folder_path": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = ListM365Files().run(folder_path=params.get("folder_path", ""))
    except Exception as e:
        result = {"success": False, "response": f"list_m365_files error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
