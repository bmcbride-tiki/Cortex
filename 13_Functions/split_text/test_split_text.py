# =============================================================================
# test_split_text.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   Checks that split_text.py's `run()` splits on a given/default
#   delimiter and selects the right segment, and fails cleanly on an
#   out-of-range index.
#
# WHAT IT INTERACTS WITH
#   - `split_text.py`, the file under test.
# =============================================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from split_text import SplitText


def test_splits_and_selects_segment():
    result = SplitText().run("a,b,c", delimiter=",", index=1)
    assert result == {"success": True, "text": "b"}


def test_default_delimiter_is_newline():
    result = SplitText().run("line1\nline2", index=1)
    assert result["text"] == "line2"


def test_out_of_range_index_fails_cleanly():
    result = SplitText().run("a,b", delimiter=",", index=5)
    assert result["success"] is False


if __name__ == "__main__":
    test_splits_and_selects_segment()
    test_default_delimiter_is_newline()
    test_out_of_range_index_fails_cleanly()
    print("All split_text self-checks passed.")
