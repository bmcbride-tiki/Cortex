# =============================================================================
# get_excel_range.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   A Task: reads a cell range from an Excel workbook via Graph's Workbook API.
#
# WHAT IT INTERACTS WITH
#   - `14_Adapters/m365_graph_bridge/m365_graph_bridge.py`'s
#     `get_excel_range()`, called directly in-process (no subprocess).
#     Mock-mode until a real Azure AD app registration exists.
#   - `test_get_excel_range.py`, this file's paired test.
#   - `core_router.py`/`server.py`, which pass this Task its
#     `file_path`/`worksheet`/`range_address` as a JSON payload.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "m365_graph_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from m365_graph_bridge import get_excel_range as _get_excel_range


class GetExcelRange:
    """Reads a cell range from an Excel workbook via Graph's Workbook API. Reuses
    m365_graph_bridge's mock logic directly (no subprocess). Mock-mode until an Azure
    AD app registration exists."""

    def run(self, file_path: str, worksheet: str, range_address: str) -> dict:
        try:
            return {"success": True, **_get_excel_range(file_path, worksheet, range_address)}
        except Exception as e:
            return {"success": False, "response": f"get_excel_range error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"file_path": "...", "worksheet": "...", "range_address": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = GetExcelRange().run(
            file_path=params.get("file_path", ""),
            worksheet=params.get("worksheet", ""),
            range_address=params.get("range_address", ""),
        )
    except Exception as e:
        result = {"success": False, "response": f"get_excel_range error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
