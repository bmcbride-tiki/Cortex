import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from list_teams_channels import ListTeamsChannels


def test_run_returns_channels():
    result = ListTeamsChannels().run("team_1")
    assert result["success"] is True
    assert len(result["channels"]) >= 1


if __name__ == "__main__":
    test_run_returns_channels()
    print("All list_teams_channels self-checks passed.")
