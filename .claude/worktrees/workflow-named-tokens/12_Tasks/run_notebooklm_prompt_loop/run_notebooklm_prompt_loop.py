# =============================================================================
# run_notebooklm_prompt_loop.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   A Task: asks a NotebookLM notebook a sequence of questions and collects
#   the answers. Mock-mode until real API/MCP access exists (see
#   notebooklm_bridge.py).
#
# WHAT IT INTERACTS WITH
#   - `14_Adapters/notebooklm_bridge/notebooklm_bridge.py`'s
#     `prompt_loop()`, called directly in-process (no subprocess).
#   - `test_run_notebooklm_prompt_loop.py`, this file's paired test.
#   - `core_router.py`/`server.py`, which pass this Task its
#     `notebook_id`/`prompts` as a JSON payload.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "notebooklm_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from notebooklm_bridge import prompt_loop as _prompt_loop


class RunNotebookLMPromptLoop:
    """Asks a NotebookLM notebook a sequence of questions and collects the
    answers. Reuses notebooklm_bridge's prompt_loop() function directly (no
    subprocess) -- mock-mode until real API/MCP access exists."""

    def run(self, notebook_id: str, prompts: list) -> dict:
        if not notebook_id:
            return {"success": False, "response": "A notebook_id is required."}
        if not prompts:
            return {"success": False, "response": "At least one prompt is required."}
        try:
            return {"success": True, **_prompt_loop(notebook_id, prompts)}
        except Exception as e:
            return {"success": False, "response": f"run_notebooklm_prompt_loop error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"notebook_id": "...", "prompts": ["..."]}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = RunNotebookLMPromptLoop().run(
            notebook_id=params.get("notebook_id", ""),
            prompts=params.get("prompts", []),
        )
    except Exception as e:
        result = {"success": False, "response": f"run_notebooklm_prompt_loop error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
