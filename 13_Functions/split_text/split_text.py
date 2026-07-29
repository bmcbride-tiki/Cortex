# =============================================================================
# split_text.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   A Function: splits text on a delimiter and returns the segment at a
#   given index.
#
# WHAT IT INTERACTS WITH
#   - No adapter/database/file dependency -- pure in-memory text transform.
#   - `test_split_text.py`, this file's paired test.
#   - `core_router.py`/`workflow_engine.py`, which dispatch this Function
#     the same way as any Task (generic `09_Functions` category), passing
#     its `text`/`delimiter`/`index` as a JSON payload.
# =============================================================================

import sys
import json
from typing import Dict, Any


class SplitText:
    """Splits text on a delimiter and returns the segment at a given index. Extracted
    from workflow_engine.py's function_split node so it can run standalone or be
    dropped into a workflow (dispatched via CoreRouter's generic 09_Functions path)."""

    def run(self, text: str, delimiter: str = "\n", index: int = 0) -> Dict[str, Any]:
        segments = text.split(delimiter or "\n")
        if index < 0 or index >= len(segments):
            return {"success": False, "response": f"Split index {index} out of range (0-{len(segments) - 1})."}
        return {"success": True, "text": segments[index]}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"text": "...", "delimiter": "\\n", "index": 0}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = SplitText().run(
            text=params.get("text", ""),
            delimiter=params.get("delimiter", "\n"),
            index=int(params.get("index") or 0),
        )
    except Exception as e:
        result = {"success": False, "response": f"split_text error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
