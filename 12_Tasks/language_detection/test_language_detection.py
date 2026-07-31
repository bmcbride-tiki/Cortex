# Copyright 2025 Brian McBride at Tiki-1 Studio
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import language_detection as mod


def test_missing_text_fails_without_touching_bridge():
    result = mod.LanguageDetection().run("")
    assert result["success"] is False


def test_run_returns_response():
    with patch.object(mod, "_ask_gemini", return_value="French") as mock_call:
        result = mod.LanguageDetection().run("Bonjour le monde")
        assert result["success"] is True
        assert result["response"] == "French"
        assert "Bonjour le monde" in mock_call.call_args[0][0]


if __name__ == "__main__":
    test_missing_text_fails_without_touching_bridge()
    test_run_returns_response()
    print("All language_detection self-checks passed.")
