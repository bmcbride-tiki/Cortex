import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from get_onenote_page_content import GetOnenotePageContent


def test_run_returns_html():
    result = GetOnenotePageContent().run("page_1")
    assert result["success"] is True
    assert "<html>" in result["content_html"]


if __name__ == "__main__":
    test_run_returns_html()
    print("All get_onenote_page_content self-checks passed.")
