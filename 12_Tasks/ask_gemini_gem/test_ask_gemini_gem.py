# Copyright 2025 Brian McBride at Tiki-1 Studio
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ask_gemini_gem as mod


def test_missing_gem_name_fails_without_touching_bridge():
    result = mod.AskGeminiGem().run("", "What should I study?")
    assert result["success"] is False


def test_missing_prompt_fails_without_touching_bridge():
    result = mod.AskGeminiGem().run("Career Coach", "")
    assert result["success"] is False


def test_run_returns_response():
    with patch.object(mod, "_ask_gemini_gem", return_value="Mocked gem answer") as mock_call:
        result = mod.AskGeminiGem().run("Career Coach", "What should I study?")
        assert result["success"] is True
        assert result["response"] == "Mocked gem answer"
        mock_call.assert_called_once_with("Career Coach", "What should I study?")


if __name__ == "__main__":
    test_missing_gem_name_fails_without_touching_bridge()
    test_missing_prompt_fails_without_touching_bridge()
    test_run_returns_response()
    print("All ask_gemini_gem self-checks passed.")
