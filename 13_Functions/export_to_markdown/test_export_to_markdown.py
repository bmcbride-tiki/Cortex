import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_to_markdown import ExportToMarkdown


def test_writes_text_as_is():
    with tempfile.TemporaryDirectory() as tmp:
        result = ExportToMarkdown().run("# Heading\n\nBody", tmp, "out")
        assert result["success"] is True
        assert Path(result["file_path"]).read_text() == "# Heading\n\nBody"
        assert Path(result["file_path"]).suffix == ".md"


if __name__ == "__main__":
    test_writes_text_as_is()
    print("All export_to_markdown self-checks passed.")
