import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import upload_notebooklm_sources as mod


def test_missing_notebook_id_fails_without_touching_bridge():
    result = mod.UploadNotebookLMSources().run("", ["a.pdf"])
    assert result["success"] is False


def test_missing_file_paths_fails_without_touching_bridge():
    result = mod.UploadNotebookLMSources().run("nb_test", [])
    assert result["success"] is False


def test_run_returns_sources():
    fake_sources = {"sources": [{"source_id": "src_1", "filename": "a.pdf", "status": "processed"}]}
    with patch.object(mod, "_upload_sources", return_value=fake_sources) as mock_call:
        result = mod.UploadNotebookLMSources().run("nb_test", ["a.pdf"])
        assert result["success"] is True
        assert result["sources"] == fake_sources["sources"]
        mock_call.assert_called_once_with("nb_test", ["a.pdf"])


if __name__ == "__main__":
    test_missing_notebook_id_fails_without_touching_bridge()
    test_missing_file_paths_fails_without_touching_bridge()
    test_run_returns_sources()
    print("All upload_notebooklm_sources self-checks passed.")
