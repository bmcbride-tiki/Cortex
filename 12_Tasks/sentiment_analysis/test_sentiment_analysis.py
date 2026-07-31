# Copyright 2025 Brian McBride at Tiki-1 Studio
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sentiment_analysis as mod


def test_missing_text_fails_without_touching_bridge():
    result = mod.SentimentAnalysis().run("")
    assert result["success"] is False


def test_run_returns_response():
    with patch.object(mod, "_ask_gemini", return_value="Positive. The tone is upbeat.") as mock_call:
        result = mod.SentimentAnalysis().run("I love this!", language="English")
        assert result["success"] is True
        assert result["response"] == "Positive. The tone is upbeat."
        prompt = mock_call.call_args[0][0]
        assert "I love this!" in prompt
        assert "English" in prompt


if __name__ == "__main__":
    test_missing_text_fails_without_touching_bridge()
    test_run_returns_response()
    print("All sentiment_analysis self-checks passed.")
