# =============================================================================
# upload_notebooklm_sources.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   A Task: uploads source files (PDF/Docx/JSON) to a NotebookLM notebook.
#   Mock-mode until real API/MCP access exists (see notebooklm_bridge.py).
#
# WHAT IT INTERACTS WITH
#   - `14_Adapters/notebooklm_bridge/notebooklm_bridge.py`'s
#     `upload_sources()`, called directly in-process (no subprocess).
#   - `test_upload_notebooklm_sources.py`, this file's paired test.
#   - `core_router.py`/`server.py`, which pass this Task its
#     `notebook_id`/`file_paths` as a JSON payload.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "notebooklm_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from notebooklm_bridge import upload_sources as _upload_sources


class UploadNotebookLMSources:
    """Uploads source files to a NotebookLM notebook. Reuses
    notebooklm_bridge's upload_sources() function directly (no subprocess) --
    mock-mode until real API/MCP access exists. Still validates that every
    given file path is a real file on disk, even in mock mode."""

    def run(self, notebook_id: str, file_paths: list) -> dict:
        if not notebook_id:
            return {"success": False, "response": "A notebook_id is required."}
        if not file_paths:
            return {"success": False, "response": "At least one file path is required."}
        try:
            return {"success": True, **_upload_sources(notebook_id, file_paths)}
        except Exception as e:
            return {"success": False, "response": f"upload_notebooklm_sources error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"notebook_id": "...", "file_paths": ["..."]}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = UploadNotebookLMSources().run(
            notebook_id=params.get("notebook_id", ""),
            file_paths=params.get("file_paths", []),
        )
    except Exception as e:
        result = {"success": False, "response": f"upload_notebooklm_sources error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
