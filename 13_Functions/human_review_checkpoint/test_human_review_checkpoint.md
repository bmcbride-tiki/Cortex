---
tool_id: 'test_human_review_checkpoint'
title: 'Human Review Checkpoint Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, function/human-in-the-loop, connects/human-review-checkpoint]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# test-human-review-checkpoint

> **Status:** Active. Runnable both via `pytest` and directly (`python test_human_review_checkpoint.py`).

## Purpose

Confirms [[human_review_checkpoint]]'s `run()` writes a real review file in each supported format (docx/json/markdown), inserts a real `workflow_checkpoints` row, defaults to docx when no format is given, and rejects an unsupported format cleanly.

## Processing Logic

* `test_docx_format_writes_file_and_checkpoint_row` -- writes a real `.docx` and confirms a positive `checkpoint_id` came back.
* `test_json_format_wraps_non_json_text` -- non-JSON content gets wrapped as `{"content": ...}` in the written `.json` file.
* `test_markdown_format_writes_as_is` -- markdown content is written unchanged.
* `test_unsupported_format_fails_cleanly` -- `fmt="pdf"` returns `success: false`.
* `test_blank_format_defaults_to_docx` -- an empty `fmt` defaults to `.docx` output.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

⚠ These tests write real rows into `brain_state.db`'s `workflow_checkpoints` table via the real `get_db_connection()` -- they do not mock the database. Running this test suite leaves real "pending" checkpoint rows behind (harmless for local dev, but worth knowing before running it against a shared database).
