---
tool_id: 'test_import_from_word'
title: 'Import from Word Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, scope/docx, connects/import-from-word]
---

# test-import-from-word

> **Status:** Active. Runnable both via `pytest` and directly (`python test_import_from_word.py`).

## Purpose

Confirms [[import_from_word]]'s `run()` extracts real paragraph text from a real generated `.docx`, and fails cleanly on a missing file.

## Processing Logic

* `test_reads_paragraphs` -- generates a throwaway two-paragraph `.docx` and confirms the joined text matches exactly.
* `test_missing_file_fails_cleanly` -- a nonexistent path returns `success: false`.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Generates its own throwaway `.docx` via `python-docx` rather than relying on a fixture file, keeping the test self-contained.
