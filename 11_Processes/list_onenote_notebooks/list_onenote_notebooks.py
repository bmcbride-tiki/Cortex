# =============================================================================
# list_onenote_notebooks.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   A zero-input, one-click Process: lists the signed-in user's OneNote
#   notebooks.
#
# WHAT IT INTERACTS WITH
#   - `14_Adapters/m365_graph_bridge/m365_graph_bridge.py`'s
#     `list_onenote_notebooks()`, called directly in-process (no
#     subprocess). Mock-mode until a real Azure AD app registration exists.
#   - `test_list_onenote_notebooks.py`, this file's paired test.
#   - `core_router.py`, which discovers and launches this script the same
#     way as every other Process.
# =============================================================================

import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "m365_graph_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from m365_graph_bridge import list_onenote_notebooks as _list_onenote_notebooks


class ListOnenoteNotebooks:
    """Zero-input, click-and-run: lists the signed-in user's OneNote notebooks. Reuses
    m365_graph_bridge's mock logic directly (no subprocess). Mock-mode until an Azure
    AD app registration exists."""

    def run(self) -> dict:
        try:
            return {"success": True, **_list_onenote_notebooks()}
        except Exception as e:
            return {"success": False, "response": f"list_onenote_notebooks error: {e}"}


if __name__ == "__main__":
    print(ListOnenoteNotebooks().run())
