import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import list_copilot_agents as mod


def test_run_returns_agents():
    with patch.object(mod, "list_agents", return_value=[{"name": "Hal-9000", "description": "Test agent"}]):
        result = mod.ListCopilotAgents().run()
        assert result["success"] is True
        assert result["agents"][0]["name"] == "Hal-9000"


def test_run_handles_browser_error():
    with patch.object(mod, "list_agents", side_effect=RuntimeError("No signed-in session")):
        result = mod.ListCopilotAgents().run()
        assert result["success"] is False


if __name__ == "__main__":
    test_run_returns_agents()
    test_run_handles_browser_error()
    print("All list_copilot_agents self-checks passed.")
