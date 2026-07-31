# Copyright 2025 Brian McBride at Tiki-1 Studio
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import summarize_text as mod


def test_missing_text_content_fails_without_touching_bridge():
    result = mod.SummarizeText().run("")
    assert result["success"] is False


def test_run_returns_response():
    with patch.object(mod, "_ask_gemini", return_value="Mocked summary") as mock_call:
        result = mod.SummarizeText().run("A long body of text.")
        assert result["success"] is True
        assert result["response"] == "Mocked summary"
        assert "A long body of text." in mock_call.call_args[0][0]


if __name__ == "__main__":
    test_missing_text_content_fails_without_touching_bridge()
    test_run_returns_response()
    print("All summarize_text self-checks passed.")
