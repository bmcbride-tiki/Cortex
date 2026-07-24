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
