# =============================================================================
# list_outlook_calendar_events.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   A Task: lists Outlook calendar events between a start and end date.
#
# WHAT IT INTERACTS WITH
#   - `14_Adapters/m365_graph_bridge/m365_graph_bridge.py`'s
#     `list_calendar_events()`, called directly in-process (no subprocess).
#     Mock-mode until a real Azure AD app registration exists.
#   - `test_list_outlook_calendar_events.py`, this file's paired test.
#   - `core_router.py`/`server.py`, which pass this Task its
#     `start_date`/`end_date` as a JSON payload.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "m365_graph_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from m365_graph_bridge import list_calendar_events


class ListOutlookCalendarEvents:
    """Lists Outlook calendar events in a date range. Reuses m365_graph_bridge's mock
    logic directly (no subprocess). Mock-mode until an Azure AD app registration
    exists."""

    def run(self, start_date: str, end_date: str) -> dict:
        try:
            return {"success": True, **list_calendar_events(start_date, end_date)}
        except Exception as e:
            return {"success": False, "response": f"list_outlook_calendar_events error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"start_date": "...", "end_date": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = ListOutlookCalendarEvents().run(start_date=params.get("start_date", ""), end_date=params.get("end_date", ""))
    except Exception as e:
        result = {"success": False, "response": f"list_outlook_calendar_events error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
