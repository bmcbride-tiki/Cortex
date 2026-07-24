import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from get_excel_range import GetExcelRange


def test_run_returns_values():
    result = GetExcelRange().run("Budget.xlsx", "Sheet1", "A1:B2")
    assert result["success"] is True
    assert len(result["values"]) == 2


if __name__ == "__main__":
    test_run_returns_values()
    print("All get_excel_range self-checks passed.")
