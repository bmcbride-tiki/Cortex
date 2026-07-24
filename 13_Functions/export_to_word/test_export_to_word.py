import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_to_word import ExportToWord


def test_writes_docx():
    with tempfile.TemporaryDirectory() as tmp:
        result = ExportToWord().run("Line one\nLine two", tmp, "out")
        assert result["success"] is True
        out_path = Path(result["file_path"])
        assert out_path.exists()
        assert out_path.suffix == ".docx"

        from docx import Document
        doc = Document(str(out_path))
        assert [p.text for p in doc.paragraphs] == ["Line one", "Line two"]


if __name__ == "__main__":
    test_writes_docx()
    print("All export_to_word self-checks passed.")
