# =============================================================================
# import_from_word.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   A Function: reads a local .docx file's paragraphs and returns the
#   extracted text.
#
# WHAT IT INTERACTS WITH
#   - `python-docx` (`Document`), for the actual paragraph-text extraction.
#   - `test_import_from_word.py`, this file's paired test.
#   - `core_router.py`/`workflow_engine.py`, which dispatch this Function
#     the same way as any Task (generic `09_Functions` category), passing
#     its `file_path` as a JSON payload.
# =============================================================================

import sys
import json
from pathlib import Path
from typing import Dict, Any


class ImportFromWord:
    """Reads a local .docx file's paragraphs and returns the extracted text. Extracted
    from workflow_engine.py's function_import_word node (_read_word_import) so it can
    run standalone or be dropped into a workflow (dispatched via CoreRouter's generic
    09_Functions path)."""

    def run(self, file_path: str) -> Dict[str, Any]:
        from docx import Document

        src = Path(file_path)
        if not src.exists():
            return {"success": False, "response": f"File not found: {src}"}

        doc = Document(str(src))
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        return {"success": True, "text": text}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"file_path": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = ImportFromWord().run(file_path=params.get("file_path", ""))
    except Exception as e:
        result = {"success": False, "response": f"import_from_word error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
