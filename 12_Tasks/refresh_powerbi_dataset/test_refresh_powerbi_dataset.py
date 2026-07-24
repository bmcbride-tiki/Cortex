# =============================================================================
# test_refresh_powerbi_dataset.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   Checks that refresh_powerbi_dataset.py's `run()` returns a successful
#   result with a real-looking refresh request ID, using
#   m365_graph_bridge's existing mock data.
#
# WHAT IT INTERACTS WITH
#   - `refresh_powerbi_dataset.py`, the file under test.
# =============================================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from refresh_powerbi_dataset import RefreshPowerbiDataset


def test_run_returns_refresh_id():
    result = RefreshPowerbiDataset().run("dataset_123")
    assert result["success"] is True
    assert result["refresh_request_id"].startswith("refresh_")


if __name__ == "__main__":
    test_run_returns_refresh_id()
    print("All refresh_powerbi_dataset self-checks passed.")
