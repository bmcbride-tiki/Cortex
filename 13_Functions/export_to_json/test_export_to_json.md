---
tool_id: 'test_export_to_json'
title: 'Export to JSON Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, scope/json, connects/export-to-json]
---

# test-export-to-json

> **Status:** Active. Runnable both via `pytest` and directly (`python test_export_to_json.py`).

## Purpose

Confirms [[export_to_json]]'s `run()` re-formats already-valid JSON and wraps non-JSON text in `{"content": ...}`, writing real files to a temporary folder.

## Processing Logic

* `test_valid_json_reformatted` -- valid JSON input round-trips to the same parsed value.
* `test_non_json_text_wrapped` -- plain text gets wrapped as `{"content": "plain text"}`.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Uses a real `tempfile.TemporaryDirectory()` rather than mocking the filesystem, since this Function's only real behavior is file I/O.
