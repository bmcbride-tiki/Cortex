import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from search_outlook_email import SearchOutlookEmail


def test_run_filters_by_sender():
    result = SearchOutlookEmail().run(query="curriculum", sender="registrar", folder="inbox", top=10)
    assert result["success"] is True
    assert len(result["messages"]) == 1


if __name__ == "__main__":
    test_run_filters_by_sender()
    print("All search_outlook_email self-checks passed.")
