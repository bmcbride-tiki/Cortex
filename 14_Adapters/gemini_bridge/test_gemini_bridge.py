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


def test_list_gems_mock_mode_returns_realistic_shape():
    with patch.object(mod, "MOCK_MODE", True):
        gems = mod.list_gems()
        assert isinstance(gems, list) and len(gems) > 0
        assert all({"id", "name", "description"} <= set(g.keys()) for g in gems)


def test_ask_gemini_gem_requires_gem_name_and_prompt():
    try:
        mod.ask_gemini_gem("", "Some prompt")
        assert False, "expected ValueError"
    except ValueError:
        pass
    try:
        mod.ask_gemini_gem("Career Coach", "")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_ask_gemini_gem_mock_mode_names_the_gem():
    with patch.object(mod, "MOCK_MODE", True):
        response = mod.ask_gemini_gem("Career Coach", "What should I study?")
        assert "Career Coach" in response
        assert "What should I study?" in response


def test_ask_gemini_gem_real_mode_looks_up_by_name_and_raises_if_missing():
    fake_gem = object()
    fake_jar = {"g1": fake_gem}

    class FakeGemJar(dict):
        def get(self, id=None, name=None, default=None):
            return fake_gem if name == "Career Coach" else default

    async def _fake_fetch_gems(*args, **kwargs):
        return FakeGemJar(fake_jar)

    async def _fake_ask_async_with_gem(*args, **kwargs):
        assert kwargs.get("gem") is fake_gem
        return "gem response"

    with patch.object(mod, "MOCK_MODE", False), \
         patch.object(mod, "_get_session_cookies", return_value=("psid", "psidts")), \
         patch.object(mod, "_fetch_gems_async", side_effect=_fake_fetch_gems), \
         patch.object(mod, "_ask_async", side_effect=_fake_ask_async_with_gem):
        response = mod.ask_gemini_gem("Career Coach", "What should I study?")
        assert response == "gem response"

    with patch.object(mod, "MOCK_MODE", False), \
         patch.object(mod, "_get_session_cookies", return_value=("psid", "psidts")), \
         patch.object(mod, "_fetch_gems_async", side_effect=_fake_fetch_gems):
        try:
            mod.ask_gemini_gem("Nonexistent Gem", "Hi")
            assert False, "expected RuntimeError"
        except RuntimeError:
            pass


if __name__ == "__main__":
    test_ask_gemini_mock_mode_includes_file_note()
    test_ask_gemini_mock_mode_no_files_note_when_none()
    test_ask_gemini_files_and_deep_research_raises()
    test_ask_gemini_passes_files_through_to_async_call()
    test_list_gems_mock_mode_returns_realistic_shape()
    test_ask_gemini_gem_requires_gem_name_and_prompt()
    test_ask_gemini_gem_mock_mode_names_the_gem()
    test_ask_gemini_gem_real_mode_looks_up_by_name_and_raises_if_missing()
    print("All gemini_bridge self-checks passed.")
