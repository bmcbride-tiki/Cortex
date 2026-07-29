# =============================================================================
# test_download_m365_file.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   Checks that download_m365_file.py's `run()` actually writes a local
#   file to a temporary folder, using m365_graph_bridge's existing mock data.
#
# WHAT IT INTERACTS WITH
#   - `download_m365_file.py`, the file under test.
# =============================================================================

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from download_m365_file import DownloadM365File


def test_run_writes_local_file():
    with tempfile.TemporaryDirectory() as tmp:
        result = DownloadM365File().run("/Reports/Budget.xlsx", tmp)
        assert result["success"] is True
        assert Path(result["local_path"]).exists()


if __name__ == "__main__":
    test_run_writes_local_file()
    print("All download_m365_file self-checks passed.")
