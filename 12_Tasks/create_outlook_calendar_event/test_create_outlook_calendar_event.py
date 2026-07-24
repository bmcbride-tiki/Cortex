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
