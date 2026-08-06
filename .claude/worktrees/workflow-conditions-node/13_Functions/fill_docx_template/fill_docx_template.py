# =============================================================================
# fill_docx_template.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   A Function: fills every `{{ content }}`/`{{content}}` token in a .docx
#   template with a single block of text and writes the completed file.
#   For templates with several distinct named placeholders instead of one,
#   see `populate_word_template_from_json.py`.
#
# WHAT IT INTERACTS WITH
#   - The given `template_path` .docx file, read via `python-docx`.
#   - `02_vault/generated/` (default output location if `output_dir` isn't
#     given).
#   - `test_fill_docx_template.py`, this file's paired test.
#   - `core_router.py`/`workflow_engine.py`, which dispatch this Function
#     the same way as any Task (generic `09_Functions` category), passing
#     its `content_text`/`template_path`/`output_dir` as a JSON payload.
# =============================================================================

import sys
import json
import time
from pathlib import Path
from typing import Dict, Any


class FillDocxTemplate:
    """Fills {{ content }} tokens in a .docx template with given text and writes the
    completed file. Extracted from workflow_engine.py's builtin_template_generator node
    (_run_template_generator) so it can run standalone or be dropped into a workflow
    (dispatched via CoreRouter's generic 09_Functions path)."""

    def run(self, content_text: str, template_path: str, output_dir: str = "") -> Dict[str, Any]:
        if not template_path:
            return {"success": False, "response": "A template_path is required."}

        from docx import Document

        src = Path(template_path)
        if not src.exists():
            return {"success": False, "response": f"Template file not found: {src}"}

        doc = Document(str(src))
        for para in doc.paragraphs:
            for token in ("{{ content }}", "{{content}}"):
                if token in para.text:
                    for run in para.runs:
                        run.text = run.text.replace(token, content_text)

        out_dir = Path(output_dir) if output_dir else Path(__file__).resolve().parents[2] / "02_vault" / "generated"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"generated_{int(time.time())}.docx"
        doc.save(str(out_path))

        return {"success": True, "file_path": str(out_path)}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"content_text": "...", "template_path": "...", "output_dir": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = FillDocxTemplate().run(
            content_text=params.get("content_text", ""),
            template_path=params.get("template_path", ""),
            output_dir=params.get("output_dir", ""),
        )
    except Exception as e:
        result = {"success": False, "response": f"fill_docx_template error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
