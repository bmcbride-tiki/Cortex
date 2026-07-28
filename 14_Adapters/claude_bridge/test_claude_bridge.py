import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import claude_bridge as cb


def test_ask_returns_mock_response():
    result = cb.ask("What is the capital of France?")
    assert result["response"].startswith("[MOCK Claude response]")
    assert "What is the capital of France?" in result["response"]


def test_mock_mode_off_fails_clearly():
    cb.MOCK_MODE = False
    try:
        try:
            cb.ask("Anything")
            assert False, "expected RuntimeError when MOCK_MODE is off"
        except RuntimeError as e:
            assert "not configured" in str(e)
    finally:
        cb.MOCK_MODE = True


if __name__ == "__main__":
    test_ask_returns_mock_response()
    test_mock_mode_off_fails_clearly()
    print("All claude_bridge self-checks passed.")
