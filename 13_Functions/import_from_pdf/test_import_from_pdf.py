import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_from_pdf import ImportFromPdf


def test_reads_pdf_text():
    with tempfile.TemporaryDirectory() as tmp:
        from fpdf import FPDF
        src = Path(tmp) / "in.pdf"
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.cell(0, 10, text="Hello PDF")
        pdf.output(str(src))

        result = ImportFromPdf().run(str(src))
        assert result["success"] is True
        assert "Hello PDF" in result["text"]


def test_missing_file_fails_cleanly():
    result = ImportFromPdf().run("/no/such/file.pdf")
    assert result["success"] is False
    assert "not found" in result["response"]


if __name__ == "__main__":
    test_reads_pdf_text()
    test_missing_file_fails_cleanly()
    print("All import_from_pdf self-checks passed.")
