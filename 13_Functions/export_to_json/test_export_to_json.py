import sys
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_to_json import ExportToJson


def test_valid_json_reformatted():
    with tempfile.TemporaryDirectory() as tmp:
        result = ExportToJson().run('{"a": 1}', tmp, "out")
        assert result["success"] is True
        assert json.loads(Path(result["file_path"]).read_text()) == {"a": 1}


def test_non_json_text_wrapped():
    with tempfile.TemporaryDirectory() as tmp:
        result = ExportToJson().run("plain text", tmp, "out2")
        payload = json.loads(Path(result["file_path"]).read_text())
        assert payload == {"content": "plain text"}


if __name__ == "__main__":
    test_valid_json_reformatted()
    test_non_json_text_wrapped()
    print("All export_to_json self-checks passed.")
