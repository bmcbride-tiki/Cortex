# =============================================================================
# test_model_classifications.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   Automated checks confirming `model_classifications.py`'s "most
#   restrictive AI model wins" logic actually behaves as documented -- that
#   a single model reports its own classification level, that mixing models
#   correctly reports the strictest one among them, and that an empty or
#   unrecognized model list reports nothing rather than guessing.
#
# WHAT IT INTERACTS WITH
#   - `model_classifications.py`'s `classification_ceiling()`, the single
#     function under test here.
#
# KEY FUNCTIONALITY NOTES
#   - No test framework (pytest, unittest) required -- every check is a
#     plain function using Python's built-in `assert`, runnable either via
#     `pytest test_model_classifications.py` or directly as
#     `python test_model_classifications.py` (see the `__main__` block,
#     which calls all three in order and prints a pass message).
# =============================================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from model_classifications import classification_ceiling


def test_single_model_returns_its_own_level():
    assert classification_ceiling(["copilot"]) == "protected_b"
    assert classification_ceiling(["gemini"]) == "protected_a"
    assert classification_ceiling(["chatgpt"]) == "public"
    assert classification_ceiling(["agenty"]) == "public"  # ABC Builder


def test_most_restrictive_model_wins():
    assert classification_ceiling(["copilot", "gemini"]) == "protected_a"
    assert classification_ceiling(["copilot", "chatgpt"]) == "public"
    assert classification_ceiling(["gemini", "notebooklm"]) == "protected_a"
    # ABC Builder (Public) caps the ceiling even alongside a stricter model.
    assert classification_ceiling(["copilot", "agenty"]) == "public"


def test_empty_or_unknown_returns_none():
    assert classification_ceiling([]) is None
    assert classification_ceiling(["some_unknown_model"]) is None


if __name__ == "__main__":
    test_single_model_returns_its_own_level()
    test_most_restrictive_model_wins()
    test_empty_or_unknown_returns_none()
    print("All model_classifications self-checks passed.")
