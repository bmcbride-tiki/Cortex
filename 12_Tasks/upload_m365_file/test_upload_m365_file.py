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
