# Copyright 2025 Brian McBride at Tiki-1 Studio
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ask_copilot as mod


def test_missing_prompt_fails_without_touching_browser():
    result = mod.AskCopilot().run("")
    assert result["success"] is False


def test_run_returns_response():
    with patch.object(mod, "_ask_copilot", return_value="Mocked Copilot answer"):
        result = mod.AskCopilot().run("Summarize this.")
        assert result["success"] is True
        assert result["response"] == "Mocked Copilot answer"


if __name__ == "__main__":
    test_missing_prompt_fails_without_touching_browser()
    test_run_returns_response()
    print("All ask_copilot self-checks passed.")
