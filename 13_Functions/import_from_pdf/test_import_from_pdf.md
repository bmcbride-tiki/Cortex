---
tool_id: 'test_import_from_pdf'
title: 'Import from PDF Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, scope/pdf, connects/import-from-pdf]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# test-import-from-pdf

> **Status:** Active. Runnable both via `pytest` and directly (`python test_import_from_pdf.py`).

## Purpose

Confirms [[import_from_pdf]]'s `run()` extracts real text from a real generated `.pdf`, and fails cleanly on a missing file.

## Processing Logic

* `test_reads_pdf_text` -- generates a throwaway `.pdf` via `fpdf2` and confirms its text comes back.
* `test_missing_file_fails_cleanly` -- a nonexistent path returns `success: false` with "not found" in the message.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Generates its own throwaway `.pdf` via `fpdf2` rather than relying on a fixture file, keeping the test self-contained.
