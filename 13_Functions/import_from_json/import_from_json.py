# =============================================================================
# import_from_json.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   A Function: reads a local .json file and returns its pretty-printed
#   contents as text.
#
# WHAT IT INTERACTS WITH
#   - The given local `.json` file, read directly off disk.
#   - `test_import_from_json.py`, this file's paired test.
#   - `core_router.py`/`workflow_engine.py`, which dispatch this Function
#     the same way as any Task (generic `09_Functions` category), passing
#     its `file_path` as a JSON payload.
# =============================================================================

import sys
import json
from pathlib import Path
from typing import Dict, Any


class ImportFromJson:
    """Reads a local .json file and returns its pretty-printed contents as text.
    Extracted from workflow_engine.py's function_import_json node so it can run
    standalone or be dropped into a workflow (dispatched via CoreRouter's generic
    09_Functions path)."""

    def run(self, file_path: str) -> Dict[str, Any]:
        src = Path(file_path)
        if not src.exists():
            return {"success": False, "response": f"File not found: {src}"}

        text = json.dumps(json.loads(src.read_text(encoding="utf-8")), indent=2)
        return {"success": True, "text": text}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"file_path": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = ImportFromJson().run(file_path=params.get("file_path", ""))
    except Exception as e:
        result = {"success": False, "response": f"import_from_json error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
