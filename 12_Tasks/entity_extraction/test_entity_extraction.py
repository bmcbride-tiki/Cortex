# Copyright 2025 Brian McBride at Tiki-1 Studio
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import entity_extraction as mod


def test_missing_text_fails_without_touching_bridge():
    result = mod.EntityExtraction().run("")
    assert result["success"] is False


def test_run_returns_response():
    with patch.object(mod, "_ask_gemini", return_value='[{"text": "Alice", "type": "person"}]') as mock_call:
        result = mod.EntityExtraction().run("Alice sent the report on Friday.")
        assert result["success"] is True
        assert result["response"] == '[{"text": "Alice", "type": "person"}]'
        assert "Alice sent the report" in mock_call.call_args[0][0]


if __name__ == "__main__":
    test_missing_text_fails_without_touching_bridge()
    test_run_returns_response()
    print("All entity_extraction self-checks passed.")
