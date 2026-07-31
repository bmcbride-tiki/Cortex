# Copyright 2025 Brian McBride at Tiki-1 Studio
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import business_card_id_reader as mod


def test_missing_file_path_fails_without_touching_bridge():
    result = mod.BusinessCardIdReader().run("")
    assert result["success"] is False


def test_nonexistent_file_fails_without_touching_bridge():
    result = mod.BusinessCardIdReader().run("C:/definitely/not/a/real/path.png")
    assert result["success"] is False
    assert "not found" in result["response"].lower()


def test_run_returns_response():
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        temp_path = f.name
    try:
        with patch.object(mod, "_ask_gemini", return_value='{"name": "Alice"}') as mock_call:
            result = mod.BusinessCardIdReader().run(temp_path)
            assert result["success"] is True
            assert result["response"] == '{"name": "Alice"}'
            assert mock_call.call_args.kwargs["files"] == [temp_path]
    finally:
        Path(temp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    test_missing_file_path_fails_without_touching_bridge()
    test_nonexistent_file_fails_without_touching_bridge()
    test_run_returns_response()
    print("All business_card_id_reader self-checks passed.")
