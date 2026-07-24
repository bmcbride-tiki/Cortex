# =============================================================================
# create_outlook_calendar_event.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   A Task: creates an Outlook calendar event (subject, start/end time,
#   attendees).
#
# WHAT IT INTERACTS WITH
#   - `14_Adapters/m365_graph_bridge/m365_graph_bridge.py`'s
#     `create_calendar_event()`, called directly in-process (no
#     subprocess). Mock-mode until a real Azure AD app registration exists.
#   - `test_create_outlook_calendar_event.py`, this file's paired test.
#   - `core_router.py`/`server.py`, which pass this Task its event details
#     as a JSON payload.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "m365_graph_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from m365_graph_bridge import create_calendar_event


class CreateOutlookCalendarEvent:
    """Creates an Outlook calendar event. Reuses m365_graph_bridge's mock logic
    directly (no subprocess). Mock-mode until an Azure AD app registration exists."""

    def run(self, subject: str, start: str, end: str, attendees: str) -> dict:
        try:
            return {"success": True, **create_calendar_event(subject, start, end, attendees)}
        except Exception as e:
            return {"success": False, "response": f"create_outlook_calendar_event error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"subject": "...", "start": "...", "end": "...", "attendees": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = CreateOutlookCalendarEvent().run(
            subject=params.get("subject", ""),
            start=params.get("start", ""),
            end=params.get("end", ""),
            attendees=params.get("attendees", ""),
        )
    except Exception as e:
        result = {"success": False, "response": f"create_outlook_calendar_event error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
