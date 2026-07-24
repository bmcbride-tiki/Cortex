# =============================================================================
# test_upload_m365_file.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   Checks that upload_m365_file.py's `run()` returns a successful result
#   with a real-looking item ID, using a real temporary local file and
#   m365_graph_bridge's existing mock upload logic.
#
# WHAT IT INTERACTS WITH
#   - `upload_m365_file.py`, the file under test.
# =============================================================================

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from upload_m365_file import UploadM365File


def test_run_uploads_real_file():
    with tempfile.TemporaryDirectory() as tmp:
        real_file = Path(tmp) / "report.docx"
        real_file.write_text("content")
        result = UploadM365File().run(str(real_file), "/Reports/report.docx")
        assert result["success"] is True
        assert result["item_id"].startswith("item_")


if __name__ == "__main__":
    test_run_uploads_real_file()
    print("All upload_m365_file self-checks passed.")
