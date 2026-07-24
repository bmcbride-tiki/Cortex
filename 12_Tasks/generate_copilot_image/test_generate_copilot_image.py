import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_copilot_image as mod


def test_missing_prompt_fails_without_touching_browser():
    result = mod.GenerateCopilotImage().run("", "/some/dir")
    assert result["success"] is False


def test_missing_output_dir_fails_without_touching_browser():
    result = mod.GenerateCopilotImage().run("a robot", "")
    assert result["success"] is False


def test_run_returns_file_path():
    with patch.object(mod, "generate_image", return_value="/some/dir/image.png"):
        result = mod.GenerateCopilotImage().run("a robot", "/some/dir")
        assert result["success"] is True
        assert result["file_path"] == "/some/dir/image.png"


if __name__ == "__main__":
    test_missing_prompt_fails_without_touching_browser()
    test_missing_output_dir_fails_without_touching_browser()
    test_run_returns_file_path()
    print("All generate_copilot_image self-checks passed.")
