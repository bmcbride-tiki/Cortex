# =============================================================================
# human_review_checkpoint.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   A Function: the app's one real human-in-the-loop mechanism. Writes
#   upstream workflow content out to a real file (.docx/.json/.md) for a
#   person to open and edit, and registers a row in the
#   `workflow_checkpoints` table so it shows up in the Cortex web app's
#   Review Queue page, where someone can mark it resolved.
#
# WHAT IT INTERACTS WITH
#   - `00_System/database.py`'s `get_db_connection()`, writing a `pending`
#     row into `workflow_checkpoints`.
#   - `python-docx`, for the `.docx` output format.
#   - `server.py`'s `GET /api/workflow-checkpoints` / `POST
#     /api/workflow-checkpoints/{id}/resolve` endpoints and the Review
#     Queue page, the other side of this checkpoint's lifecycle.
#   - `test_human_review_checkpoint.py`, this file's paired test.
#   - `core_router.py`/`workflow_engine.py`, which dispatch this Function
#     the same way as any Task (generic `09_Functions` category).
# =============================================================================

import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

CURRENT_DIR = Path(__file__).resolve().parent
PARENT_DIR = CURRENT_DIR.parents[1]
CORE_DIR = PARENT_DIR / "00_System"

if str(CORE_DIR) not in sys.path:
    sys.path.append(str(CORE_DIR))

from database import get_db_connection

SUPPORTED_FORMATS = {"docx", "json", "markdown"}


class HumanReviewCheckpoint:
    """
    Ends a workflow run at a human hand-off point: writes the upstream content out to a
    real file for a person to open and edit, and registers a row in the workflow_checkpoints
    table so it shows up in the Review Queue page. Dispatched exactly like any other
    13_Functions/Task/Process script -- see workflow_engine.py's generic execute_app_logic
    dispatch for kind="function"/category="09_Functions" nodes.
    """

    def _write_docx(self, out_path: Path, text: str) -> None:
        # Same shape as workflow_engine.py's _write_word_export: one paragraph per line.
        from docx import Document
        doc = Document()
        for line in text.split("\n"):
            doc.add_paragraph(line)
        doc.save(str(out_path))

    def _write_json(self, out_path: Path, text: str) -> None:
        import json
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = {"content": text}
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _write_markdown(self, out_path: Path, text: str) -> None:
        out_path.write_text(text, encoding="utf-8")

    def _write_review_file(self, output_dir: Path, filename: str, fmt: str, content_text: str) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        extension = ".docx" if fmt == "docx" else (".json" if fmt == "json" else ".md")
        out_path = output_dir / f"{filename}{extension}"

        if fmt == "docx":
            self._write_docx(out_path, content_text)
        elif fmt == "json":
            self._write_json(out_path, content_text)
        else:
            self._write_markdown(out_path, content_text)

        return out_path

    def run(
        self,
        content_text: str,
        output_dir: str,
        filename: str,
        fmt: str,
        instructions: str,
        workflow_label: str,
    ) -> Dict[str, Any]:
        report: Dict[str, Any] = {"success": True, "errors": []}

        fmt = (fmt or "docx").strip().lower()
        if fmt not in SUPPORTED_FORMATS:
            report["success"] = False
            report["errors"].append(f"Unsupported format '{fmt}'. Expected one of: {sorted(SUPPORTED_FORMATS)}.")
            return report

        filename = filename.strip() or f"review_{int(datetime.now().timestamp())}"
        workflow_label = workflow_label.strip() or "Unlabeled Workflow"

        try:
            out_path = self._write_review_file(Path(output_dir), filename, fmt, content_text)
        except Exception as e:
            report["success"] = False
            report["errors"].append(f"Could not write review file: {e}")
            return report

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO workflow_checkpoints (
                    workflow_label, node_title, instructions, file_path, status
                ) VALUES (?, ?, ?, ?, 'pending');
            """, (workflow_label, "Human Review Checkpoint", instructions.strip(), str(out_path)))
            conn.commit()
            checkpoint_id = cursor.lastrowid
        finally:
            conn.close()

        report["checkpoint_id"] = checkpoint_id
        report["file_path"] = str(out_path)
        report["message"] = (
            f"Workflow paused for human review (checkpoint #{checkpoint_id}). "
            f"File written to: {out_path}"
        )
        return report


if __name__ == "__main__":
    import json

    if len(sys.argv) < 2:
        print(json.dumps({
            "success": False,
            "errors": ['Expected one JSON payload arg: {"content_text": "...", "output_dir": "...", "filename": "...", "format": "docx", "instructions": "...", "workflow_label": "..."}'],
        }))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        checkpoint = HumanReviewCheckpoint()
        result = checkpoint.run(
            content_text=params.get("content_text", ""),
            output_dir=params.get("output_dir", ""),
            filename=params.get("filename", ""),
            fmt=params.get("format", ""),
            instructions=params.get("instructions", ""),
            workflow_label=params.get("workflow_label", ""),
        )
    except Exception as e:
        result = {"success": False, "errors": [f"human_review_checkpoint error: {e}"]}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
