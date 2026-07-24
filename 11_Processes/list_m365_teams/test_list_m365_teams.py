import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from list_m365_teams import ListM365Teams


def test_run_returns_teams():
    result = ListM365Teams().run()
    assert result["success"] is True
    assert len(result["teams"]) >= 1


if __name__ == "__main__":
    test_run_returns_teams()
    print("All list_m365_teams self-checks passed.")
