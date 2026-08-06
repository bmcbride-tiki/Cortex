# =============================================================================
# list_m365_teams.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   A zero-input, one-click Process: lists the Microsoft Teams the
#   signed-in M365 user belongs to.
#
# WHAT IT INTERACTS WITH
#   - `14_Adapters/m365_graph_bridge/m365_graph_bridge.py`'s `list_teams()`,
#     called directly in-process (no subprocess). Mock-mode until a real
#     Azure AD app registration exists.
#   - `test_list_m365_teams.py`, this file's paired test.
#   - `core_router.py`, which discovers and launches this script the same
#     way as every other Process.
# =============================================================================

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
