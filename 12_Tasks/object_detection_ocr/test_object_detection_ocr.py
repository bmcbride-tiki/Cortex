# Copyright 2025 Brian McBride at Tiki-1 Studio
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import object_detection_ocr as mod


def test_missing_file_path_fails_without_touching_bridge():
    result = mod.ObjectDetectionOcr().run("")
    assert result["success"] is False


def test_nonexistent_file_fails_without_touching_bridge():
    result = mod.ObjectDetectionOcr().run("C:/definitely/not/a/real/path.png")
    assert result["success"] is False
    assert "not found" in result["response"].lower()


def test_run_returns_response():
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        temp_path = f.name
    try:
        with patch.object(mod, "_ask_gemini", return_value='{"objects": ["sign"], "text": "STOP"}') as mock_call:
            result = mod.ObjectDetectionOcr().run(temp_path)
            assert result["success"] is True
            assert result["response"] == '{"objects": ["sign"], "text": "STOP"}'
            assert mock_call.call_args.kwargs["files"] == [temp_path]
    finally:
        Path(temp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    test_missing_file_path_fails_without_touching_bridge()
    test_nonexistent_file_fails_without_touching_bridge()
    test_run_returns_response()
    print("All object_detection_ocr self-checks passed.")
