# =============================================================================
# test_human_review_checkpoint.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   Checks that human_review_checkpoint.py's `run()` writes a real review
#   file in each supported format (docx/json/markdown), inserts a real
#   `workflow_checkpoints` row, defaults to docx when no format is given,
#   and rejects an unsupported format cleanly.
#
# WHAT IT INTERACTS WITH
#   - `human_review_checkpoint.py`, the file under test.
#   - `00_System/database.py`'s real `get_db_connection()` -- these tests
#     write real rows into `brain_state.db`'s `workflow_checkpoints` table,
#     they don't mock the database.
# =============================================================================

import sys
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from human_review_checkpoint import HumanReviewCheckpoint


def test_docx_format_writes_file_and_checkpoint_row():
    with tempfile.TemporaryDirectory() as tmp:
        checkpoint = HumanReviewCheckpoint()
        result = checkpoint.run(
            content_text="Line one\nLine two",
            output_dir=tmp,
            filename="test_review",
            fmt="docx",
            instructions="Check formatting.",
            workflow_label="Test Workflow",
        )
        assert result["success"] is True
        assert result["checkpoint_id"] > 0
        out_path = Path(result["file_path"])
        assert out_path.exists()
        assert out_path.suffix == ".docx"


def test_json_format_wraps_non_json_text():
    with tempfile.TemporaryDirectory() as tmp:
        checkpoint = HumanReviewCheckpoint()
        result = checkpoint.run(
            content_text="not valid json",
            output_dir=tmp,
            filename="test_review_json",
            fmt="json",
            instructions="",
            workflow_label="Test Workflow",
        )
        assert result["success"] is True
        out_path = Path(result["file_path"])
        payload = json.loads(out_path.read_text(encoding="utf-8"))
        assert payload == {"content": "not valid json"}


def test_markdown_format_writes_as_is():
    with tempfile.TemporaryDirectory() as tmp:
        checkpoint = HumanReviewCheckpoint()
        result = checkpoint.run(
            content_text="# Heading\n\nSome text.",
            output_dir=tmp,
            filename="test_review_md",
            fmt="markdown",
            instructions="",
            workflow_label="Test Workflow",
        )
        assert result["success"] is True
        out_path = Path(result["file_path"])
        assert out_path.read_text(encoding="utf-8") == "# Heading\n\nSome text."


def test_unsupported_format_fails_cleanly():
    checkpoint = HumanReviewCheckpoint()
    result = checkpoint.run(
        content_text="text",
        output_dir=tempfile.gettempdir(),
        filename="whatever",
        fmt="pdf",
        instructions="",
        workflow_label="Test Workflow",
    )
    assert result["success"] is False
    assert "Unsupported format" in result["errors"][0]


def test_blank_format_defaults_to_docx():
    with tempfile.TemporaryDirectory() as tmp:
        checkpoint = HumanReviewCheckpoint()
        result = checkpoint.run(
            content_text="text",
            output_dir=tmp,
            filename="test_review_default",
            fmt="",
            instructions="",
            workflow_label="Test Workflow",
        )
        assert result["success"] is True
        assert Path(result["file_path"]).suffix == ".docx"


if __name__ == "__main__":
    test_docx_format_writes_file_and_checkpoint_row()
    test_json_format_wraps_non_json_text()
    test_markdown_format_writes_as_is()
    test_unsupported_format_fails_cleanly()
    test_blank_format_defaults_to_docx()
    print("All human_review_checkpoint self-checks passed.")
