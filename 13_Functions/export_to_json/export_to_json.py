# =============================================================================
# export_to_json.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   A Function: writes text to a new .json file. If the text is already
#   valid JSON it's re-saved neatly formatted; otherwise it's wrapped in
#   `{"content": ...}` so the output file is always valid JSON either way.
#
# WHAT IT INTERACTS WITH
#   - No adapter/database dependency -- pure file I/O against whatever
#     `output_dir` it's given.
#   - `test_export_to_json.py`, this file's paired test.
#   - `core_router.py`/`workflow_engine.py`, which dispatch this Function
#     the same way as any Task (generic `09_Functions` category), passing
#     its `text`/`output_dir`/`filename` as a JSON payload.
# =============================================================================

import sys
import json
import time
from pathlib import Path
from typing import Dict, Any


class ExportToJson:
    """
    Writes text to a new .json file. If the text is already valid JSON it's re-saved
    neatly formatted; otherwise it's wrapped in {"content": ...} so the output file is
    always valid JSON either way. Standalone-capable: same logic previously lived inline
    in workflow_engine.py's function_export_json node (_write_json_export), extracted here
    so it can run on its own or be dropped into a workflow (dispatched via CoreRouter, see
    workflow_engine.py's generic 09_Functions path).
    """

    def run(self, text: str, output_dir: str, filename: str = "") -> Dict[str, Any]:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = (filename or f"export_{int(time.time())}").strip()
        if not filename.endswith(".json"):
            filename += ".json"
        out_path = out_dir / filename

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = {"content": text}
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        return {"success": True, "file_path": str(out_path)}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"text": "...", "output_dir": "...", "filename": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = ExportToJson().run(
            text=params.get("text", ""),
            output_dir=params.get("output_dir", ""),
            filename=params.get("filename", ""),
        )
    except Exception as e:
        result = {"success": False, "response": f"export_to_json error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
