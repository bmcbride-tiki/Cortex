# Copyright 2025 Brian McBride at Tiki-1 Studio
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ask_copilot_agent as mod


def test_missing_agent_name_fails_without_touching_browser():
    result = mod.AskCopilotAgent().run("", "prompt")
    assert result["success"] is False


def test_missing_prompt_fails_without_touching_browser():
    result = mod.AskCopilotAgent().run("Hal-9000", "")
    assert result["success"] is False


def test_run_returns_response():
    with patch.object(mod, "ask_agent", return_value="Mocked agent answer"):
        result = mod.AskCopilotAgent().run("Hal-9000", "What is the status?")
        assert result["success"] is True
        assert result["response"] == "Mocked agent answer"


if __name__ == "__main__":
    test_missing_agent_name_fails_without_touching_browser()
    test_missing_prompt_fails_without_touching_browser()
    test_run_returns_response()
    print("All ask_copilot_agent self-checks passed.")
