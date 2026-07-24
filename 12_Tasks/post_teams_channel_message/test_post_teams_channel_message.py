import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from post_teams_channel_message import PostTeamsChannelMessage


def test_run_posts_message():
    result = PostTeamsChannelMessage().run("team_1", "channel_1", "hello")
    assert result["success"] is True
    assert result["status"] == "posted (mock)"


if __name__ == "__main__":
    test_run_posts_message()
    print("All post_teams_channel_message self-checks passed.")
