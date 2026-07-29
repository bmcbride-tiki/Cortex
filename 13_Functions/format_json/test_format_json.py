# =============================================================================
# test_format_json.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   Checks that format_json.py's `run()` pretty-prints valid JSON and
#   fails cleanly (rather than crashing) on invalid JSON.
#
# WHAT IT INTERACTS WITH
#   - `format_json.py`, the file under test.
# =============================================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from format_json import FormatJson


def test_reformats_valid_json():
    result = FormatJson().run('{"a":1}')
    assert result["success"] is True
    assert '"a": 1' in result["text"]


def test_invalid_json_fails_cleanly():
    result = FormatJson().run("not json")
    assert result["success"] is False
    assert "Invalid JSON" in result["response"]


if __name__ == "__main__":
    test_reformats_valid_json()
    test_invalid_json_fails_cleanly()
    print("All format_json self-checks passed.")
