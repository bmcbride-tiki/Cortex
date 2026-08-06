# Copyright 2025 Brian McBride at Tiki-1 Studio
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import create_notebooklm_notebook as mod


def test_run_defaults_title_when_blank():
    with patch.object(mod, "_create_notebook", return_value={"notebook_id": "nb_test", "title": "Untitled Notebook"}) as mock_call:
        result = mod.CreateNotebookLMNotebook().run("")
        assert result["success"] is True
        mock_call.assert_called_once_with("Untitled Notebook")


def test_run_returns_notebook_id():
    with patch.object(mod, "_create_notebook", return_value={"notebook_id": "nb_abc123", "title": "My Notebook"}):
        result = mod.CreateNotebookLMNotebook().run("My Notebook")
        assert result["success"] is True
        assert result["notebook_id"] == "nb_abc123"
        assert result["title"] == "My Notebook"


if __name__ == "__main__":
    test_run_defaults_title_when_blank()
    test_run_returns_notebook_id()
    print("All create_notebooklm_notebook self-checks passed.")
