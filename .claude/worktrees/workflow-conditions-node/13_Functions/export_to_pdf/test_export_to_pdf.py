# =============================================================================
# test_export_to_pdf.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   Checks that export_to_pdf.py's `run()` writes a real `.pdf` file for
#   plain text, and fails cleanly (rather than crashing) on a character
#   outside fpdf2's built-in Latin-1 font support.
#
# WHAT IT INTERACTS WITH
#   - `export_to_pdf.py`, the file under test.
# =============================================================================

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_to_pdf import ExportToPdf


def test_writes_pdf():
    with tempfile.TemporaryDirectory() as tmp:
        result = ExportToPdf().run("Hello world", tmp, "out")
        assert result["success"] is True
        out_path = Path(result["file_path"])
        assert out_path.exists()
        assert out_path.suffix == ".pdf"


def test_non_latin1_character_fails_cleanly():
    with tempfile.TemporaryDirectory() as tmp:
        result = ExportToPdf().run("emoji: \U0001F600", tmp, "out2")
        assert result["success"] is False
        assert "Latin-1" in result["response"]


if __name__ == "__main__":
    test_writes_pdf()
    test_non_latin1_character_fails_cleanly()
    print("All export_to_pdf self-checks passed.")
