import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from list_onenote_notebooks import ListOnenoteNotebooks


def test_run_returns_notebooks():
    result = ListOnenoteNotebooks().run()
    assert result["success"] is True
    assert len(result["notebooks"]) >= 1


if __name__ == "__main__":
    test_run_returns_notebooks()
    print("All list_onenote_notebooks self-checks passed.")
