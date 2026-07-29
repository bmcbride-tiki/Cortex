# =============================================================================
# test_search_outlook_email.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   Checks that search_outlook_email.py's `run()` correctly filters mock
#   messages down to the ones matching a given sender.
#
# WHAT IT INTERACTS WITH
#   - `search_outlook_email.py`, the file under test.
# =============================================================================

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
