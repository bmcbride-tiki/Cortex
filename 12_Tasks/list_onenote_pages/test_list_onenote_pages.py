import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from list_onenote_pages import ListOnenotePages


def test_run_returns_pages():
    result = ListOnenotePages().run("notebook_1")
    assert result["success"] is True
    assert len(result["pages"]) >= 1


if __name__ == "__main__":
    test_run_returns_pages()
    print("All list_onenote_pages self-checks passed.")
