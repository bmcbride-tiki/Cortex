# Copyright 2025 Brian McBride at Tiki-1 Studio
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ask_gemini as mod


def test_missing_prompt_fails_without_touching_bridge():
    result = mod.AskGemini().run("")
    assert result["success"] is False


def test_run_returns_response():
    with patch.object(mod, "_ask_gemini", return_value="Mocked Gemini answer") as mock_call:
        result = mod.AskGemini().run("Summarize this.", search=True)
        assert result["success"] is True
        assert result["response"] == "Mocked Gemini answer"
        mock_call.assert_called_once_with("Summarize this.", use_search=True)


if __name__ == "__main__":
    test_missing_prompt_fails_without_touching_bridge()
    test_run_returns_response()
    print("All ask_gemini self-checks passed.")
