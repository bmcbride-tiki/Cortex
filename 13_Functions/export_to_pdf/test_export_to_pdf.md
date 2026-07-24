---
tool_id: 'test_export_to_pdf'
title: 'Export to PDF Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, scope/pdf, connects/export-to-pdf]
---

# test-export-to-pdf

> **Status:** Active. Runnable both via `pytest` and directly (`python test_export_to_pdf.py`).

## Purpose

Confirms [[export_to_pdf]]'s `run()` writes a real `.pdf` for plain text, and fails cleanly (rather than crashing) on a character outside fpdf2's built-in Latin-1 font support.

## Processing Logic

* `test_writes_pdf` -- plain text produces a real `.pdf` file on disk.
* `test_non_latin1_character_fails_cleanly` -- an emoji character returns `success: false` with "Latin-1" in the message.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Uses a real `tempfile.TemporaryDirectory()` and real `fpdf2` calls -- no mocking, since the whole point is proving the known font limitation fails gracefully.
