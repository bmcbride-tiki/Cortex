# =============================================================================
# create_notebooklm_notebook.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   A Task: creates a new Google NotebookLM notebook. Mock-mode until real
#   API/MCP access exists (see notebooklm_bridge.py).
#
# WHAT IT INTERACTS WITH
#   - `14_Adapters/notebooklm_bridge/notebooklm_bridge.py`'s
#     `create_notebook()`, called directly in-process (no subprocess).
#   - `test_create_notebooklm_notebook.py`, this file's paired test.
#   - `core_router.py`/`server.py`, which pass this Task its `title` as a
#     JSON payload.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "notebooklm_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from notebooklm_bridge import create_notebook as _create_notebook


class CreateNotebookLMNotebook:
    """Creates a new NotebookLM notebook. Reuses notebooklm_bridge's
    create_notebook() function directly (no subprocess) -- mock-mode until
    real API/MCP access exists."""

    def run(self, title: str) -> dict:
        title = title or "Untitled Notebook"
        try:
            return {"success": True, **_create_notebook(title)}
        except Exception as e:
            return {"success": False, "response": f"create_notebooklm_notebook error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"title": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = CreateNotebookLMNotebook().run(title=params.get("title", ""))
    except Exception as e:
        result = {"success": False, "response": f"create_notebooklm_notebook error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
