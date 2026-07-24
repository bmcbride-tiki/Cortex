import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import format_text_with_copilot as mod


def test_missing_text_fails_without_touching_browser():
    result = mod.FormatTextWithCopilot().run("", "formal tone")
    assert result["success"] is False


def test_run_builds_prompt_and_returns_response():
    captured = {}

    def fake_ask_copilot(prompt, headless=True):
        captured["prompt"] = prompt
        return "Reformatted text"

    with patch.object(mod, "ask_copilot", fake_ask_copilot):
        result = mod.FormatTextWithCopilot().run("raw text", "formal briefing note")
        assert result["success"] is True
        assert result["response"] == "Reformatted text"
        assert "formal briefing note" in captured["prompt"]
        assert "raw text" in captured["prompt"]


if __name__ == "__main__":
    test_missing_text_fails_without_touching_browser()
    test_run_builds_prompt_and_returns_response()
    print("All format_text_with_copilot self-checks passed.")
