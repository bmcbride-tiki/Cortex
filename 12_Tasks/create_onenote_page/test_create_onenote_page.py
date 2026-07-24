import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from create_onenote_page import CreateOnenotePage


def test_run_creates_page():
    result = CreateOnenotePage().run("section_1", "New Page", "<p>Body</p>")
    assert result["success"] is True
    assert result["page_id"].startswith("page_")


if __name__ == "__main__":
    test_run_creates_page()
    print("All create_onenote_page self-checks passed.")
