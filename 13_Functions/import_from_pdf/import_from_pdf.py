# =============================================================================
# import_from_pdf.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   A Function: reads a local .pdf file's pages and returns the extracted
#   text.
#
# WHAT IT INTERACTS WITH
#   - `pypdf` (`PdfReader`), for the actual page-text extraction.
#   - `test_import_from_pdf.py`, this file's paired test.
#   - `core_router.py`/`workflow_engine.py`, which dispatch this Function
#     the same way as any Task (generic `09_Functions` category), passing
#     its `file_path` as a JSON payload.
# =============================================================================

import sys
import json
from pathlib import Path
from typing import Dict, Any


class ImportFromPdf:
    """Reads a local .pdf file's pages and returns the extracted text. Extracted from
    workflow_engine.py's function_import_pdf node (_read_pdf_import) so it can run
    standalone or be dropped into a workflow (dispatched via CoreRouter's generic
    09_Functions path)."""

    def run(self, file_path: str) -> Dict[str, Any]:
        from pypdf import PdfReader

        src = Path(file_path)
        if not src.exists():
            return {"success": False, "response": f"File not found: {src}"}

        reader = PdfReader(str(src))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        return {"success": True, "text": text}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"file_path": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = ImportFromPdf().run(file_path=params.get("file_path", ""))
    except Exception as e:
        result = {"success": False, "response": f"import_from_pdf error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
