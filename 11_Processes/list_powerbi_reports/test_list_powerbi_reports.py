import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from list_powerbi_reports import ListPowerbiReports


def test_run_returns_reports():
    result = ListPowerbiReports().run()
    assert result["success"] is True
    assert len(result["reports"]) >= 1


if __name__ == "__main__":
    test_run_returns_reports()
    print("All list_powerbi_reports self-checks passed.")
