# =============================================================================
# test_list_outlook_calendar_events.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   Checks that list_outlook_calendar_events.py's `run()` returns a
#   successful result with at least one event, using m365_graph_bridge's
#   existing mock data.
#
# WHAT IT INTERACTS WITH
#   - `list_outlook_calendar_events.py`, the file under test.
# =============================================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from list_outlook_calendar_events import ListOutlookCalendarEvents


def test_run_returns_events():
    result = ListOutlookCalendarEvents().run("", "")
    assert result["success"] is True
    assert len(result["events"]) >= 1


if __name__ == "__main__":
    test_run_returns_events()
    print("All list_outlook_calendar_events self-checks passed.")
