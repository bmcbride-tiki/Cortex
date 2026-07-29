# =============================================================================
# export_to_pdf.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   A Function: writes text into a new .pdf file (one line per row via
#   `fpdf2`).
#
# WHAT IT INTERACTS WITH
#   - `fpdf2` (`FPDF`), which does the actual PDF rendering. Its built-in
#     font only supports Latin-1 characters, so text outside that range
#     fails cleanly with an explanatory message rather than crashing.
#   - `test_export_to_pdf.py`, this file's paired test.
#   - `core_router.py`/`workflow_engine.py`, which dispatch this Function
#     the same way as any Task (generic `09_Functions` category), passing
#     its `text`/`output_dir`/`filename` as a JSON payload.
# =============================================================================

import sys
import json
import time
from pathlib import Path
from typing import Dict, Any


class ExportToPdf:
    """Writes text into a new .pdf file. Extracted from workflow_engine.py's
    function_export_pdf node (_write_pdf_export) so it can run standalone or be dropped
    into a workflow (dispatched via CoreRouter's generic 09_Functions path).

    Note: fpdf2's built-in font only supports Latin-1 (roughly Western European)
    characters -- text containing characters outside that range will fail to export.
    """

    def run(self, text: str, output_dir: str, filename: str = "") -> Dict[str, Any]:
        from fpdf import FPDF

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = (filename or f"export_{int(time.time())}").strip()
        if not filename.endswith(".pdf"):
            filename += ".pdf"
        out_path = out_dir / filename

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=11)
        try:
            for line in text.split("\n"):
                pdf.multi_cell(pdf.epw, 6, line)
        except Exception as e:
            return {"success": False, "response": f"PDF export failed (likely a non-Latin-1 character in the text): {e}"}
        pdf.output(str(out_path))

        return {"success": True, "file_path": str(out_path)}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"text": "...", "output_dir": "...", "filename": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = ExportToPdf().run(
            text=params.get("text", ""),
            output_dir=params.get("output_dir", ""),
            filename=params.get("filename", ""),
        )
    except Exception as e:
        result = {"success": False, "response": f"export_to_pdf error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
