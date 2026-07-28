import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ask_chatgpt as mod


def test_missing_prompt_fails_without_touching_bridge():
    result = mod.AskChatGPT().run("")
    assert result["success"] is False


def test_run_returns_response():
    with patch.object(mod, "_ask_chatgpt", return_value={"response": "Mocked ChatGPT answer"}):
        result = mod.AskChatGPT().run("Summarize this.")
        assert result["success"] is True
        assert result["response"] == "Mocked ChatGPT answer"


if __name__ == "__main__":
    test_missing_prompt_fails_without_touching_bridge()
    test_run_returns_response()
    print("All ask_chatgpt self-checks passed.")
