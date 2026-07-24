import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from list_sharepoint_sites import ListSharepointSites


def test_run_returns_sites():
    result = ListSharepointSites().run()
    assert result["success"] is True
    assert len(result["sites"]) >= 1


if __name__ == "__main__":
    test_run_returns_sites()
    print("All list_sharepoint_sites self-checks passed.")
