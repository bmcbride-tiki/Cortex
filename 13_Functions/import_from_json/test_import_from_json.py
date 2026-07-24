import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_from_json import ImportFromJson


def test_reads_and_reformats_json():
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "in.json"
        src.write_text('{"a":1}')
        result = ImportFromJson().run(str(src))
        assert result["success"] is True
        assert '"a": 1' in result["text"]


def test_missing_file_fails_cleanly():
    result = ImportFromJson().run("/no/such/file.json")
    assert result["success"] is False


if __name__ == "__main__":
    test_reads_and_reformats_json()
    test_missing_file_fails_cleanly()
    print("All import_from_json self-checks passed.")
