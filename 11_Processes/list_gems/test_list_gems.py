# Copyright 2025 Brian McBride at Tiki-1 Studio
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import list_gems as mod


def test_run_returns_gems():
    with patch.object(mod, "list_gems", return_value=[{"id": "g1", "name": "Career Coach", "description": "Test gem"}]):
        result = mod.ListGems().run()
        assert result["success"] is True
        assert result["gems"][0]["name"] == "Career Coach"


def test_run_handles_bridge_error():
    with patch.object(mod, "list_gems", side_effect=RuntimeError("No signed-in session")):
        result = mod.ListGems().run()
        assert result["success"] is False


if __name__ == "__main__":
    test_run_returns_gems()
    test_run_handles_bridge_error()
    print("All list_gems self-checks passed.")
