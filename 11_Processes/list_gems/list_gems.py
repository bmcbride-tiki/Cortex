# =============================================================================
# list_gems.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   A zero-input, one-click Process: lists the Gems available on the signed-in
#   Gemini account (name + description) -- Gemini's equivalent of M365 Copilot
#   Agents (see list_copilot_agents).
#
# WHAT IT INTERACTS WITH
#   - `14_Adapters/gemini_bridge/gemini_bridge.py`'s `list_gems()`, called
#     directly in-process (no subprocess). Runs in mock mode by default
#     (GEMINI_MOCK_MODE) until a real signed-in session is configured.
#   - `test_list_gems.py`, this file's paired test.
#   - `core_router.py`, which discovers and launches this script the same
#     way as every other Process.
# =============================================================================

import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "gemini_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from gemini_bridge import list_gems


class ListGems:
    """Zero-input, click-and-run: lists the Gems available on the signed-in Gemini
    account. Reuses gemini_bridge's list_gems() directly (no subprocess) -- your
    signed-in Google session, no API key, when not in mock mode."""

    def run(self) -> dict:
        try:
            return {"success": True, "gems": list_gems()}
        except Exception as e:
            return {"success": False, "response": f"list_gems error: {e}"}


if __name__ == "__main__":
    print(ListGems().run())
