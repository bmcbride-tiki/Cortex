# Copyright 2025 Brian McBride at Tiki-1 Studio
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gemini_bridge as mod


def test_ask_gemini_mock_mode_includes_file_note():
    with patch.object(mod, "MOCK_MODE", True):
        response = mod.ask_gemini("Describe this image", files=["C:/fake/image.png"])
        assert "1 attached file" in response
        assert "Describe this image" in response


def test_ask_gemini_mock_mode_no_files_note_when_none():
    with patch.object(mod, "MOCK_MODE", True):
        response = mod.ask_gemini("Plain prompt")
        assert "attached file" not in response


def test_ask_gemini_files_and_deep_research_raises():
    try:
        mod.ask_gemini("Research this", use_search=True, files=["C:/fake/doc.pdf"])
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_ask_gemini_passes_files_through_to_async_call():
    async def _fake_ask_async(*args, **kwargs):
        return "real response"

    with patch.object(mod, "MOCK_MODE", False), \
         patch.object(mod, "_get_session_cookies", return_value=("psid", "psidts")), \
         patch.object(mod, "_ask_async", side_effect=_fake_ask_async) as mock_ask_async:
        response = mod.ask_gemini("Describe this", files=["C:/fake/image.png"])
        assert response == "real response"
        mock_ask_async.assert_called_once_with("psid", "psidts", "Describe this", deep_research=False, files=["C:/fake/image.png"])


if __name__ == "__main__":
    test_ask_gemini_mock_mode_includes_file_note()
    test_ask_gemini_mock_mode_no_files_note_when_none()
    test_ask_gemini_files_and_deep_research_raises()
    test_ask_gemini_passes_files_through_to_async_call()
    print("All gemini_bridge self-checks passed.")
