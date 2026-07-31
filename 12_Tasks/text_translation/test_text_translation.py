# Copyright 2025 Brian McBride at Tiki-1 Studio
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import text_translation as mod


def test_missing_text_fails_without_touching_bridge():
    result = mod.TextTranslation().run("", "French")
    assert result["success"] is False


def test_missing_target_language_fails_without_touching_bridge():
    result = mod.TextTranslation().run("Hello", "")
    assert result["success"] is False


def test_run_returns_response():
    with patch.object(mod, "_ask_gemini", return_value="Bonjour") as mock_call:
        result = mod.TextTranslation().run("Hello", "French", source_language="English")
        assert result["success"] is True
        assert result["response"] == "Bonjour"
        prompt = mock_call.call_args[0][0]
        assert "Hello" in prompt and "French" in prompt and "English" in prompt


if __name__ == "__main__":
    test_missing_text_fails_without_touching_bridge()
    test_missing_target_language_fails_without_touching_bridge()
    test_run_returns_response()
    print("All text_translation self-checks passed.")
