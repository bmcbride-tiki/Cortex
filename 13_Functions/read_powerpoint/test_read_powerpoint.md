---
tool_id: 'test_read_powerpoint'
title: 'Read PowerPoint Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, scope/pptx, connects/read-powerpoint]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# test-read-powerpoint

> **Status:** Active. Runnable both via `pytest` and directly (`python test_read_powerpoint.py`).

## Purpose

Confirms [[read_powerpoint]]'s `run()` extracts real slide title/body text from a real generated `.pptx`, and fails cleanly on a missing file.

## Processing Logic

* `test_reads_slide_text` -- generates a one-slide `.pptx` with a title and body, and confirms both plus the `--- Slide 1 ---` header come back.
* `test_missing_file_fails_cleanly` -- a nonexistent path returns `success: false`.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Generates its own throwaway `.pptx` via `python-pptx` rather than relying on a fixture file, keeping the test self-contained.
