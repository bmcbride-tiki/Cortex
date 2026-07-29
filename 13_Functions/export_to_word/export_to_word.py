# =============================================================================
# export_to_word.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   A Function: writes text into a new .docx file, one paragraph per line.
#
# WHAT IT INTERACTS WITH
#   - `python-docx` (`Document`), which does the actual .docx writing.
#   - `test_export_to_word.py`, this file's paired test.
#   - `core_router.py`/`workflow_engine.py`, which dispatch this Function
#     the same way as any Task (generic `09_Functions` category), passing
#     its `text`/`output_dir`/`filename` as a JSON payload.
# =============================================================================

import sys
import json
import time
from pathlib import Path
from typing import Dict, Any


class ExportToWord:
    """Writes text into a new .docx file, one paragraph per line. Extracted from
    workflow_engine.py's function_export_word node (_write_word_export) so it can run
    standalone or be dropped into a workflow (dispatched via CoreRouter's generic
    09_Functions path)."""

    def run(self, text: str, output_dir: str, filename: str = "") -> Dict[str, Any]:
        from docx import Document

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = (filename or f"export_{int(time.time())}").strip()
        if not filename.endswith(".docx"):
            filename += ".docx"
        out_path = out_dir / filename

        doc = Document()
        for line in text.split("\n"):
            doc.add_paragraph(line)
        doc.save(str(out_path))

        return {"success": True, "file_path": str(out_path)}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"text": "...", "output_dir": "...", "filename": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = ExportToWord().run(
            text=params.get("text", ""),
            output_dir=params.get("output_dir", ""),
            filename=params.get("filename", ""),
        )
    except Exception as e:
        result = {"success": False, "response": f"export_to_word error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
