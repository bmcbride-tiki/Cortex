# =============================================================================
# test_create_outlook_calendar_event.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   Checks that create_outlook_calendar_event.py's `run()` returns a
#   successful result with a real-looking event ID, using
#   m365_graph_bridge's existing mock data.
#
# WHAT IT INTERACTS WITH
#   - `create_outlook_calendar_event.py`, the file under test.
# =============================================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from create_outlook_calendar_event import CreateOutlookCalendarEvent


def test_run_creates_event():
    result = CreateOutlookCalendarEvent().run("Sync", "2026-08-01T10:00:00Z", "2026-08-01T11:00:00Z", "a@example.com")
    assert result["success"] is True
    assert result["event_id"].startswith("evt_")


if __name__ == "__main__":
    test_run_creates_event()
    print("All create_outlook_calendar_event self-checks passed.")
