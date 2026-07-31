# Copyright 2025 Brian McBride at Tiki-1 Studio
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import key_phrase_extraction as mod


def test_missing_text_fails_without_touching_bridge():
    result = mod.KeyPhraseExtraction().run("")
    assert result["success"] is False


def test_run_returns_response():
    with patch.object(mod, "_ask_gemini", return_value='["apprenticeship", "curriculum review"]') as mock_call:
        result = mod.KeyPhraseExtraction().run("The apprenticeship curriculum review is due Friday.")
        assert result["success"] is True
        assert result["response"] == '["apprenticeship", "curriculum review"]'
        assert "apprenticeship curriculum review" in mock_call.call_args[0][0]


if __name__ == "__main__":
    test_missing_text_fails_without_touching_bridge()
    test_run_returns_response()
    print("All key_phrase_extraction self-checks passed.")
