import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ask_claude as mod


def test_missing_prompt_fails_without_touching_bridge():
    result = mod.AskClaude().run("")
    assert result["success"] is False


def test_run_returns_response():
    with patch.object(mod, "_ask_claude", return_value={"response": "Mocked Claude answer"}):
        result = mod.AskClaude().run("Summarize this.")
        assert result["success"] is True
        assert result["response"] == "Mocked Claude answer"


if __name__ == "__main__":
    test_missing_prompt_fails_without_touching_bridge()
    test_run_returns_response()
    print("All ask_claude self-checks passed.")
