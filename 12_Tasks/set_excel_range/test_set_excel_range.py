# =============================================================================
# test_set_excel_range.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   Checks that set_excel_range.py's `run()` returns a successful result
#   reporting the correct number of rows written, using
#   m365_graph_bridge's existing mock data.
#
# WHAT IT INTERACTS WITH
#   - `set_excel_range.py`, the file under test.
# =============================================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from set_excel_range import SetExcelRange


def test_run_writes_range():
    result = SetExcelRange().run("Budget.xlsx", "Sheet1", "A1:B2", [["x", "y"]])
    assert result["success"] is True
    assert result["row_count"] == 1


if __name__ == "__main__":
    test_run_writes_range()
    print("All set_excel_range self-checks passed.")
