import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from list_recent_onedrive_files import ListRecentOnedriveFiles


def test_run_returns_files():
    result = ListRecentOnedriveFiles().run()
    assert result["success"] is True
    assert len(result["files"]) >= 1


if __name__ == "__main__":
    test_run_returns_files()
    print("All list_recent_onedrive_files self-checks passed.")
