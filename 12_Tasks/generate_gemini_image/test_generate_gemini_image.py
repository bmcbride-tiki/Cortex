import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_gemini_image as mod


def test_missing_prompt_fails_without_touching_bridge():
    result = mod.GenerateGeminiImage().run("", "C:/tmp")
    assert result["success"] is False


def test_missing_output_dir_fails_without_touching_bridge():
    result = mod.GenerateGeminiImage().run("a cat", "")
    assert result["success"] is False


def test_run_returns_file_path():
    with patch.object(mod, "_generate_image", return_value="C:/tmp/gemini_image_mock_1.png") as mock_call:
        result = mod.GenerateGeminiImage().run("a cat", "C:/tmp")
        assert result["success"] is True
        assert result["file_path"] == "C:/tmp/gemini_image_mock_1.png"
        mock_call.assert_called_once_with("a cat", "C:/tmp")


if __name__ == "__main__":
    test_missing_prompt_fails_without_touching_bridge()
    test_missing_output_dir_fails_without_touching_bridge()
    test_run_returns_file_path()
    print("All generate_gemini_image self-checks passed.")
