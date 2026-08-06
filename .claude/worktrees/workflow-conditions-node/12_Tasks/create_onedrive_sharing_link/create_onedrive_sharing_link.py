# =============================================================================
# create_onedrive_sharing_link.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   A Task: creates a shareable link for a OneDrive file, given its path.
#
# WHAT IT INTERACTS WITH
#   - `14_Adapters/m365_graph_bridge/m365_graph_bridge.py`'s
#     `create_onedrive_sharing_link()`, called directly in-process (no
#     subprocess). Mock-mode until a real Azure AD app registration exists.
#   - `test_create_onedrive_sharing_link.py`, this file's paired test.
#   - `core_router.py`/`server.py`, which pass this Task its `file_path`
#     argument as a JSON payload when launched from the Workflow Builder or
#     a Tasks-page popup.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "m365_graph_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from m365_graph_bridge import create_onedrive_sharing_link as _create_onedrive_sharing_link


class CreateOnedriveSharingLink:
    """Creates a shareable link for a OneDrive file. Reuses m365_graph_bridge's mock
    logic directly (no subprocess). Mock-mode until an Azure AD app registration
    exists."""

    def run(self, file_path: str) -> dict:
        try:
            return {"success": True, **_create_onedrive_sharing_link(file_path)}
        except Exception as e:
            return {"success": False, "response": f"create_onedrive_sharing_link error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"file_path": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = CreateOnedriveSharingLink().run(file_path=params.get("file_path", ""))
    except Exception as e:
        result = {"success": False, "response": f"create_onedrive_sharing_link error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
