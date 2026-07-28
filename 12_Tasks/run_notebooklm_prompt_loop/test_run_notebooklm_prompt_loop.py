import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_notebooklm_prompt_loop as mod


def test_missing_notebook_id_fails_without_touching_bridge():
    result = mod.RunNotebookLMPromptLoop().run("", ["What is X?"])
    assert result["success"] is False


def test_missing_prompts_fails_without_touching_bridge():
    result = mod.RunNotebookLMPromptLoop().run("nb_test", [])
    assert result["success"] is False


def test_run_returns_qa_pairs():
    fake_qa = {"qa_pairs": [{"prompt": "What is X?", "response": "X is..."}]}
    with patch.object(mod, "_prompt_loop", return_value=fake_qa) as mock_call:
        result = mod.RunNotebookLMPromptLoop().run("nb_test", ["What is X?"])
        assert result["success"] is True
        assert result["qa_pairs"] == fake_qa["qa_pairs"]
        mock_call.assert_called_once_with("nb_test", ["What is X?"])


if __name__ == "__main__":
    test_missing_notebook_id_fails_without_touching_bridge()
    test_missing_prompts_fails_without_touching_bridge()
    test_run_returns_qa_pairs()
    print("All run_notebooklm_prompt_loop self-checks passed.")
