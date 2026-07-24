# =============================================================================
# claude_bridge.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   Adapter for Anthropic Claude. There is no API key configured for this
#   project yet, so every action runs in MOCK_MODE by default -- it returns
#   realistic-shaped fake data instead of calling the real Claude API. The
#   action names, parameters, and response shape are the real contract; once
#   a real ANTHROPIC_API_KEY exists, only the inside of `ask()` needs to
#   change (a real call would use the `anthropic` Python SDK's
#   `client.messages.create(model=..., messages=[...], max_tokens=...)`).
#
# WHAT IT INTERACTS WITH
#   - `core_router.py`, which is what actually runs this file when
#     `workflow_engine.py`'s `function_claude_ask` node dispatches to it
#     (same mechanism gemini_bridge.py/notebooklm_bridge.py use).
#
# KEY FUNCTIONALITY NOTES
#   - Same MOCK_MODE / JSON-line contract as notebooklm_bridge.py: dry_run
#     (workflow_engine.py's own concept) means "don't call any adapter yet";
#     MOCK_MODE means "this adapter has no real backend to call yet, so
#     simulate one realistically." With MOCK_MODE off and no real backend
#     wired in, `ask` fails clearly instead of pretending to succeed.
#   - Claude is not in this project's official information-security
#     classification list yet (see 00_System/model_classifications.py) --
#     it defaults to the most conservative level (Public) until officially
#     classified.
# =============================================================================

# 14_Adapters/claude_bridge/claude_bridge.py
import sys
sys.dont_write_bytecode = True

import os
import json
import argparse
from typing import Any, Dict

MOCK_MODE = os.environ.get("CLAUDE_MOCK_MODE", "1") != "0"

NOT_CONFIGURED_MESSAGE = (
    "Claude API access is not configured yet. Set CLAUDE_MOCK_MODE=1 (the default) "
    "to use simulated responses, or wire up a real ANTHROPIC_API_KEY and the "
    "anthropic Python SDK inside claude_bridge.py."
)


def ask(prompt: str) -> Dict[str, Any]:
    if not MOCK_MODE:
        raise RuntimeError(NOT_CONFIGURED_MESSAGE)
    return {"response": f"[MOCK Claude response] {prompt[:300]}"}


def main():
    # Expects one command-line argument: a small JSON instruction, e.g.
    #   {"action": "ask", "prompt": "..."}
    # Always prints back exactly one line of JSON: either
    # {"success": true, ...} or {"success": false, "response": "<error>"}.
    parser = argparse.ArgumentParser(description="Workbrain Claude Integration Bridge (mock-mode until a real API key exists)")
    parser.add_argument("payload", nargs="?", default="", help="Inline JSON parameter from router")
    args = parser.parse_args()

    if not args.payload:
        print(json.dumps({
            "success": False,
            "response": 'No JSON payload provided. Expected: {"action": "ask", "prompt": "..."}',
        }))
        sys.exit(1)

    try:
        params = json.loads(args.payload)
    except json.JSONDecodeError as e:
        print(json.dumps({"success": False, "response": f"Malformed JSON payload: {e}"}))
        sys.exit(1)

    action = params.get("action", "ask")

    try:
        if action == "ask":
            result = {"success": True, **ask(params.get("prompt", ""))}
        else:
            result = {"success": False, "response": f"Unknown action: {action}"}
    except Exception as e:
        result = {"success": False, "response": f"Claude bridge error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)


if __name__ == "__main__":
    main()
