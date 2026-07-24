# =============================================================================
# test_web_scrape.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   Checks that web_scrape.py's `run()` rejects a missing `url` before
#   attempting any real network request.
#
# WHAT IT INTERACTS WITH
#   - `web_scrape.py`, the file under test.
#
# KEY FUNCTIONALITY NOTES
#   - Deliberately doesn't test the real-fetch path (no mocking of
#     `requests`/`lxml` here) -- a real network call to an arbitrary URL
#     isn't something a fast, repeatable unit test should depend on.
# =============================================================================

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
