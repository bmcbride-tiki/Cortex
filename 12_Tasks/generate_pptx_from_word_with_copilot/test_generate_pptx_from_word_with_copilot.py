import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_pptx_from_word_with_copilot import GeneratePptxFromWordWithCopilot


def test_run_generates_pptx():
    with tempfile.TemporaryDirectory() as tmp:
        from docx import Document
        src = Path(tmp) / "source.docx"
        doc = Document()
        doc.add_paragraph("Section 1: Introduction")
        doc.add_paragraph("Body text.")
        doc.save(str(src))

        result = GeneratePptxFromWordWithCopilot().run(str(src), tmp, "")
        assert result["success"] is True
        assert Path(result["file_path"]).exists()


if __name__ == "__main__":
    test_run_generates_pptx()
    print("All generate_pptx_from_word_with_copilot self-checks passed.")
