import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from web_scrape import WebScrape


def test_missing_url_fails_cleanly():
    result = WebScrape().run("")
    assert result["success"] is False
    assert "url is required" in result["response"]


if __name__ == "__main__":
    test_missing_url_fails_cleanly()
    print("All web_scrape self-checks passed.")
