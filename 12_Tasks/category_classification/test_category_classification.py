# Copyright 2025 Brian McBride at Tiki-1 Studio
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import category_classification as mod


def test_missing_text_fails_without_touching_bridge():
    result = mod.CategoryClassification().run("", "Urgent, Normal")
    assert result["success"] is False


def test_missing_categories_fails_without_touching_bridge():
    result = mod.CategoryClassification().run("Please review ASAP", "")
    assert result["success"] is False


def test_run_returns_response():
    with patch.object(mod, "_ask_gemini", return_value="Urgent") as mock_call:
        result = mod.CategoryClassification().run("Please review ASAP", "Urgent, Normal, Low Priority")
        assert result["success"] is True
        assert result["response"] == "Urgent"
        prompt = mock_call.call_args[0][0]
        assert "Please review ASAP" in prompt and "Urgent, Normal, Low Priority" in prompt


if __name__ == "__main__":
    test_missing_text_fails_without_touching_bridge()
    test_missing_categories_fails_without_touching_bridge()
    test_run_returns_response()
    print("All category_classification self-checks passed.")
