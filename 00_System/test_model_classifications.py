import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from model_classifications import classification_ceiling


def test_single_model_returns_its_own_level():
    assert classification_ceiling(["copilot"]) == "protected_b"
    assert classification_ceiling(["gemini"]) == "protected_a"
    assert classification_ceiling(["chatgpt"]) == "public"


def test_most_restrictive_model_wins():
    assert classification_ceiling(["copilot", "gemini"]) == "protected_a"
    assert classification_ceiling(["copilot", "chatgpt"]) == "public"
    assert classification_ceiling(["gemini", "notebooklm"]) == "protected_a"


def test_empty_or_unknown_returns_none():
    assert classification_ceiling([]) is None
    assert classification_ceiling(["some_unknown_model"]) is None


if __name__ == "__main__":
    test_single_model_returns_its_own_level()
    test_most_restrictive_model_wins()
    test_empty_or_unknown_returns_none()
    print("All model_classifications self-checks passed.")
